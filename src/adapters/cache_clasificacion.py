"""
CommunityLab AI - Caché de clasificaciones por mensaje
Un mensaje ya clasificado con el mismo prompt no vuelve a la IA: reprocesar un lote (o solaparlo con otro) es instantáneo.
La clave es un hash del prompt y de los campos que ve el modelo, así que cambiar el prompt invalida la caché sola.
"""
import hashlib
import json
import os
import threading
from typing import Any, Dict, List, Optional

from src import config
from src.utils.logger import setup_logger

logger = setup_logger("cache_clasificacion")
_bloqueo = threading.Lock()
_memoria: Optional[Dict[str, Dict[str, Any]]] = None


def _version_prompt(prompt) -> str:
    return hashlib.sha256(repr(prompt.messages).encode("utf-8")).hexdigest()[:12]


def clave(prompt, mensaje: Dict[str, Any], campos: List[str]) -> str:
    datos = {c: mensaje.get(c) for c in campos if c != "message_id"}
    base = _version_prompt(prompt) + json.dumps(datos, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _cargar() -> Dict[str, Dict[str, Any]]:
    global _memoria
    if _memoria is None:
        try:
            _memoria = json.loads(config.ARCHIVO_CACHE.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            _memoria = {}
    return _memoria


def obtener(claves: List[str]) -> Dict[str, Dict[str, Any]]:
    """Las entradas guardadas para las claves pedidas (las que no están, no aparecen)."""
    if not config.USAR_CACHE:
        return {}
    with _bloqueo:
        memoria = _cargar()
        return {k: memoria[k] for k in claves if k in memoria}


def guardar(nuevas: Dict[str, Dict[str, Any]]) -> None:
    if not config.USAR_CACHE or not nuevas:
        return
    with _bloqueo:
        memoria = _cargar()
        memoria.update(nuevas)
        try:
            config.ARCHIVO_CACHE.parent.mkdir(parents=True, exist_ok=True)
            temporal = config.ARCHIVO_CACHE.with_suffix(".tmp")
            temporal.write_text(json.dumps(memoria, ensure_ascii=False), encoding="utf-8")
            os.replace(temporal, config.ARCHIVO_CACHE)  # escritura atómica: nunca queda un JSON a medias
        except OSError as error:
            logger.warning(f"No se pudo guardar la caché ({type(error).__name__}); se sigue sin ella")
