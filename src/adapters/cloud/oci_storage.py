"""
CommunityLab AI - Storage Adapter (Local Emulation & Future OCI Client)
Persiste el paquete de distribución completo (Formato B) en la ruta que define spec.md:
generated/YYYY-MM-DD/<paquete_id>.json. Hoy escribe en data/processed/ (emulación local);
el cliente del SDK de OCI se conecta aquí sin cambiar la interfaz.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from src.domain.schemas import PaqueteDistribucion
from src.utils.logger import setup_logger

logger = setup_logger("oci_storage_adapter")


class ObjectStorageAdapter:
    def __init__(self, bucket_name: Optional[str] = None, namespace: Optional[str] = None):
        self.bucket_name = bucket_name or os.getenv("OCI_BUCKET_NAME", "communitylab-bucket")
        self.namespace = namespace or os.getenv("OCI_NAMESPACE", "oracle-one-latam-g10")
        self.base_dir = Path("data/processed")

    def persist_distribution_package(self, paquete: Dict[str, Any]) -> Dict[str, str]:
        """Valida el paquete contra el Formato B y lo guarda (sobrescribe la misma ruta, como pide spec.md
        cuando el panel cambia estados de curaduría). Devuelve la referencia de almacenamiento."""
        PaqueteDistribucion.model_validate(paquete)
        ruta_objeto = paquete["almacenamiento_oci"]["ruta_objeto"]
        destino = self.base_dir / ruta_objeto
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(paquete, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Paquete guardado en local: {destino}")
        return {
            "bucket": self.bucket_name,
            "namespace": self.namespace,
            "ruta_objeto": ruta_objeto,
            # "guardado_con_exito" queda reservado para cuando la subida al bucket real exista
            "status": "guardado_local",
            "local_path": str(destino),
        }
