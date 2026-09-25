"""
CommunityLab AI - Storage Adapter (Local Emulation & Future OCI Client)
Maneja la persistencia de paquetes de distribución y trazabilidad.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from src.utils.logger import setup_logger

logger = setup_logger("oci_storage_adapter")


class ObjectStorageAdapter:
    """
    Adaptador de almacenamiento para persistir los paquetes consolidados de distribución.
    Diseñado para emulación local y conmutación transparente hacia OCI Object Storage.
    """
    def __init__(self, bucket_name: Optional[str] = None, namespace: Optional[str] = None):
        self.bucket_name = bucket_name or os.getenv("OCI_BUCKET_NAME", "communitylab-bucket")
        self.namespace = namespace or os.getenv("OCI_NAMESPACE", "oracle-one-latam-g10")
        self.base_dir = Path("data/processed")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def persist_distribution_package(self, package_data: Dict[str, Any], week_tag: str = "Semana_04") -> Dict[str, str]:
        """
        Persiste el paquete final estructurado en JSON emulando la jerarquía de OCI Object Storage:
        communitylab-bucket/generated/linkedin/YYYY-MM-DD/paquete-distribucion.json
        """
        hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        dest_folder = self.base_dir / "generated" / "linkedin" / hoy
        dest_folder.mkdir(parents=True, exist_ok=True)

        filename = f"paquete-distribucion-{week_tag.lower().replace('_', '-')}.json"
        target_path = dest_folder / filename

        # Guardar en local con formato legible
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(package_data, f, ensure_ascii=False, indent=2)

        ruta_objeto = f"generated/linkedin/{hoy}/{filename}"
        logger.info(f"Paquete persistido exitosamente en: {ruta_objeto}")

        return {
            "bucket": self.bucket_name,
            "namespace": self.namespace,
            "ruta_objeto": ruta_objeto,
            "status": "guardado_con_exito",
            "local_path": str(target_path)
        }