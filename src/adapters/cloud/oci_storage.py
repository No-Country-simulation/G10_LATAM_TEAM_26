"""
CommunityLab AI - Adaptador de OCI Object Storage
Persiste el paquete de distribución (Formato B) en la ruta de spec.md: generated/YYYY-MM-DD/<paquete_id>.json, junto
con las imágenes de sus activos (generated/YYYY-MM-DD/img/<paquete_id>/<activo_id>.<ext>). Siempre deja una copia en
data/processed/ con la misma ruta; si hay credenciales de OCI, además sube todo al bucket (subida real basada en la
integración de Álvaro). La curaduría sobrescribe la misma ruta, como pide spec.md.

Credenciales (en .env, nunca en el repositorio): OCI_USER_OCID, OCI_TENANCY_OCID, OCI_FINGERPRINT, OCI_KEY_FILE y
OCI_REGION, o bien OCI_CONFIG_FILE (~/.oci/config). Además OCI_NAMESPACE y OCI_BUCKET_NAME.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from src import config
from src.domain.schemas import PaqueteDistribucion
from src.utils.logger import setup_logger

logger = setup_logger("oci_storage_adapter")

TIPOS_IMAGEN = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def _cliente_oci():
    """Cliente de Object Storage si hay credenciales completas; None para trabajar solo en local."""
    try:
        import oci
    except ImportError:
        return None
    try:
        archivo = os.getenv("OCI_CONFIG_FILE", "")
        if archivo and Path(os.path.expanduser(archivo)).exists():
            ajustes = oci.config.from_file(os.path.expanduser(archivo), os.getenv("OCI_PROFILE", "DEFAULT"))
        else:
            clave = os.getenv("OCI_KEY_FILE", "")
            if clave and not Path(clave).is_absolute():  # relativa a la raíz del proyecto (local y Docker)
                clave = str(config.RAIZ / clave)
            ajustes = {"user": os.getenv("OCI_USER_OCID", ""), "tenancy": os.getenv("OCI_TENANCY_OCID", ""),
                       "fingerprint": os.getenv("OCI_FINGERPRINT", ""), "key_file": clave,
                       "region": os.getenv("OCI_REGION", "sa-santiago-1")}
            if not (ajustes["user"] and ajustes["key_file"] and Path(ajustes["key_file"]).exists()):
                return None
        oci.config.validate_config(ajustes)
        return oci.object_storage.ObjectStorageClient(ajustes)
    except Exception as error:
        logger.warning(f"No se pudo crear el cliente de OCI ({type(error).__name__}: {error}); solo copia local")
        return None


class ObjectStorageAdapter:
    def __init__(self, bucket_name: Optional[str] = None, namespace: Optional[str] = None, cliente: Any = None):
        self.bucket_name = bucket_name or os.getenv("OCI_BUCKET_NAME", "communitylab-bucket")
        self.namespace = namespace or os.getenv("OCI_NAMESPACE", "")
        self.base_dir = config.RAIZ / "data" / "processed"
        self.client = cliente if cliente is not None else _cliente_oci()
        if self.client is not None and not self.namespace:  # el namespace se puede pedir al propio servicio
            try:
                self.namespace = self.client.get_namespace().data
            except Exception as error:
                logger.warning(f"No se pudo obtener el namespace de OCI ({type(error).__name__})")

    @property
    def conectado(self) -> bool:
        return self.client is not None and bool(self.namespace)

    def _subir(self, ruta_objeto: str, datos: bytes, tipo: str) -> None:
        self.client.put_object(namespace_name=self.namespace, bucket_name=self.bucket_name,
                               object_name=ruta_objeto, put_object_body=datos, content_type=tipo)

    def _subir_imagenes(self, paquete: Dict[str, Any]) -> int:
        carpeta = Path(paquete["almacenamiento_oci"]["ruta_objeto"]).parent.as_posix()
        subidas = 0
        for activo in paquete["activos"]:
            imagen = activo.get("imagen") or {}
            if imagen.get("estado") != "lista" or not imagen.get("ruta") or not Path(imagen["ruta"]).exists():
                continue
            ruta = Path(imagen["ruta"])
            destino = f"{carpeta}/img/{paquete['paquete_id']}/{activo['activo_id']}{ruta.suffix}"
            self._subir(destino, ruta.read_bytes(), TIPOS_IMAGEN.get(ruta.suffix.lower(), "application/octet-stream"))
            imagen["ruta_oci"] = destino
            subidas += 1
        return subidas

    def persist_distribution_package(self, paquete: Dict[str, Any]) -> Dict[str, Any]:
        """Valida el paquete contra el Formato B, lo guarda en local y, si hay cliente, lo sube al bucket con sus
        imágenes. El status sigue spec.md: guardado_con_exito (en el bucket) o guardado_local."""
        PaqueteDistribucion.model_validate(paquete)
        ruta_objeto = paquete["almacenamiento_oci"]["ruta_objeto"]
        resultado = {"bucket": self.bucket_name, "namespace": self.namespace, "ruta_objeto": ruta_objeto,
                     "status": "guardado_local", "imagenes_subidas": 0}
        if self.conectado:
            try:
                resultado["imagenes_subidas"] = self._subir_imagenes(paquete)  # antes del JSON: deja ruta_oci
                paquete["almacenamiento_oci"]["status"] = "guardado_con_exito"
                self._subir(ruta_objeto, json.dumps(paquete, ensure_ascii=False, indent=2).encode("utf-8"),
                            "application/json")
                resultado["status"] = "guardado_con_exito"
                logger.info(f"Paquete subido a OCI: {self.bucket_name}/{ruta_objeto}")
            except Exception as error:
                paquete["almacenamiento_oci"]["status"] = "guardado_local"
                resultado["error"] = f"{type(error).__name__}: {str(error)[:120]}"
                logger.error(f"No se pudo subir el paquete a OCI ({resultado['error']}); queda la copia local")
        else:
            paquete["almacenamiento_oci"]["status"] = "guardado_local"
        destino = self.base_dir / ruta_objeto
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(paquete, ensure_ascii=False, indent=2), encoding="utf-8")
        resultado["local_path"] = str(destino)
        return resultado
