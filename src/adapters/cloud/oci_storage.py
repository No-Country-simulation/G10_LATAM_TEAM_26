"""
CommunityLab AI - Adaptador OCI Object Storage
Sube paquetes JSON y archivos binarios de imagen (.png) al Bucket Always Free.
"""
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from src.utils.logger import setup_logger

logger = setup_logger("oci_storage_adapter")

try:
    import oci
    OCI_AVAILABLE = True
except ImportError:
    OCI_AVAILABLE = False


class ObjectStorageAdapter:
    def __init__(self):
        self.bucket_name = os.getenv("OCI_BUCKET_NAME", "communitylab-bucket")
        self.namespace = os.getenv("OCI_NAMESPACE", "oracle-one-latam-g10")
        self.region = os.getenv("OCI_REGION", "sa-santiago-1")
        self.base_dir = Path("data/processed")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializar cliente de OCI si las credenciales existen
        self.client = None
        self._init_oci_client()

    def _init_oci_client(self):
        """Intenta autenticarse con el SDK de OCI mediante API Key o archivo de configuración."""
        key_file = os.getenv("OCI_KEY_FILE", "")
        user_ocid = os.getenv("OCI_USER_OCID", "")
        tenancy_ocid = os.getenv("OCI_TENANCY_OCID", "")
        fingerprint = os.getenv("OCI_FINGERPRINT", "")

        if OCI_AVAILABLE and key_file and os.path.exists(key_file) and user_ocid:
            try:
                config = {
                    "user": user_ocid,
                    "key_file": key_file,
                    "fingerprint": fingerprint,
                    "tenancy": tenancy_ocid,
                    "region": self.region
                }
                oci.config.validate_config(config)
                self.client = oci.object_storage.ObjectStorageClient(config)
                logger.info("Cliente de OCI Object Storage conectado exitosamente.")
            except Exception as e:
                logger.warning(f"No se pudo inicializar OCI Object Storage Client: {e}. Se operará en modo local.")
        else:
            logger.info("Credenciales completas de OCI no detectadas en .env. Operando en emulación local estructurada.")

    def upload_image(self, local_image_path: str, message_id: str) -> Optional[str]:
        """Sube el archivo binario de la imagen (.png) al bucket de OCI."""
        p = Path(local_image_path)
        if not p.exists():
            return None

        hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        object_name = f"generated/images/{hoy}/{p.name}"

        # Subida real a Oracle Cloud si el cliente está conectado
        if self.client:
            try:
                with open(p, "rb") as f:
                    self.client.put_object(
                        namespace_name=self.namespace,
                        bucket_name=self.bucket_name,
                        object_name=object_name,
                        put_object_body=f,
                        content_type="image/png"
                    )
                logger.info(f"Imagen subida exitosamente al Bucket de OCI: {object_name}")
                return object_name
            except Exception as e:
                logger.error(f"Fallo al subir imagen a OCI Bucket: {e}")
                return None

        # Si no hay cliente cloud activo, retorna la ruta lógica estructurada
        return object_name

    def persist_distribution_package(self, package_data: Dict[str, Any], week_tag: str = "Semana_04", custom_filename: Optional[str] = None) -> Dict[str, str]:
        """Sube el JSON consolidado al Bucket de OCI garantizando nombres únicos."""
        hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Si se especifica un nombre (ej: POST-896216.json), se usa ese; si no, el del lote
        if custom_filename:
            filename = custom_filename if custom_filename.endswith(".json") else f"{custom_filename}.json"
        else:
            filename = f"paquete-distribucion-{week_tag.lower().replace('_', '-')}.json"

        object_name = f"generated/linkedin/{hoy}/{filename}"

        # 1. Copia local de respaldo
        dest_folder = self.base_dir / "generated" / "linkedin" / hoy
        dest_folder.mkdir(parents=True, exist_ok=True)
        local_target = dest_folder / filename

        with open(local_target, "w", encoding="utf-8") as f:
            json.dump(package_data, f, ensure_ascii=False, indent=2)

        # 2. Subida real a Oracle Cloud
        status_subida = "guardado_local_y_preparado"
        if self.client:
            try:
                json_bytes = json.dumps(package_data, ensure_ascii=False, indent=2).encode("utf-8")
                self.client.put_object(
                    namespace_name=self.namespace,
                    bucket_name=self.bucket_name,
                    object_name=object_name,
                    put_object_body=json_bytes,
                    content_type="application/json"
                )
                status_subida = "guardado_con_exito_en_oci_bucket"
                logger.info(f"Paquete JSON subido exitosamente a OCI Bucket: {object_name}")
            except Exception as e:
                status_subida = f"error_subida_oci: {str(e)[:60]}"
                logger.error(f"Error subiendo paquete a OCI: {e}")

        return {
            "bucket": self.bucket_name,
            "namespace": self.namespace,
            "ruta_objeto": object_name,
            "status": status_subida,
            "local_path": str(local_target)
        }