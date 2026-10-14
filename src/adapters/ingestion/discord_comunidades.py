"""
CommunityLab AI - Comunidades de Discord
Cada comunidad es una aplicación de Discord (su token) más el servidor elegido. La del .env (DISCORD_BOT_TOKEN) es
la "principal"; las demás se agregan desde el panel y se guardan en data/discord/comunidades.json, que no va al
repositorio (data/discord/ está en .gitignore). El token nunca sale del servidor: al panel solo llegan sus últimos
4 caracteres.

Cada comunidad lee y guarda por separado (carpeta, cursores, prefijo en raw/ del bucket y nombre de origen), así la
base distingue qué mensajes de cada una ya se analizaron.
"""
import json
import os
import re
import secrets
import threading
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from src import config
from src.adapters.ingestion.discord_api import CARPETA

CARPETA_COMUNIDADES = config.RAIZ / "data" / "discord"
ARCHIVO = CARPETA_COMUNIDADES / "comunidades.json"
PRINCIPAL = "principal"
_bloqueo = threading.Lock()


def _slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", texto).strip("_")[:40] or "Comunidad"


def _guardadas() -> List[Dict[str, Any]]:
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _escribir(lista: List[Dict[str, Any]]) -> None:
    CARPETA_COMUNIDADES.mkdir(parents=True, exist_ok=True)
    temporal = ARCHIVO.with_suffix(".tmp")
    temporal.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(ARCHIVO)


def _principal() -> Dict[str, Any]:
    return {
        "id": PRINCIPAL, "nombre": "Servidor principal", "servidor_id": None, "servidor": None,
        "token": os.getenv("DISCORD_BOT_TOKEN", "").strip(), "origen": "Discord_Servidor_Oficial",
        # La principal sigue leyendo data/raw/ completo: incluye las capturas que dejó el bot antes
        "carpeta": CARPETA, "raw_dir": config.RAIZ / "data" / "raw", "prefijo": "discord",
    }


def _completar(c: Dict[str, Any]) -> Dict[str, Any]:
    carpeta = CARPETA_COMUNIDADES / c["id"]
    return {**c, "carpeta": carpeta, "raw_dir": carpeta, "prefijo": f"discordcom-{c['id']}"}


def listar() -> List[Dict[str, Any]]:
    return [_principal()] + [_completar(c) for c in _guardadas()]


def obtener(comunidad_id: Optional[str]) -> Dict[str, Any]:
    for c in listar():
        if c["id"] == (comunidad_id or PRINCIPAL):
            return c
    raise KeyError(comunidad_id)


def publica(c: Dict[str, Any]) -> Dict[str, Any]:
    """Lo que puede ver el panel: sin el token."""
    token = c.get("token") or ""
    return {"id": c["id"], "nombre": c["nombre"], "servidor": c.get("servidor"), "origen": c["origen"],
            "principal": c["id"] == PRINCIPAL, "configurada": bool(token) and not token.startswith("pega-tu"),
            "token_final": f"…{token[-4:]}" if len(token) > 8 else None}


def agregar(nombre: str, token: str, servidor_id: str, servidor: str) -> Dict[str, Any]:
    nombre = nombre.strip()[:60]
    with _bloqueo:
        lista = _guardadas()
        if any(c["nombre"].lower() == nombre.lower() for c in lista) or nombre.lower() == "servidor principal":
            raise ValueError(f"Ya existe una comunidad llamada «{nombre}».")
        nueva = {"id": f"{_slug(nombre).lower()}-{secrets.token_hex(2)}", "nombre": nombre, "token": token.strip(),
                 "servidor_id": servidor_id, "servidor": servidor, "origen": f"Discord_{_slug(nombre)}"}
        _escribir(lista + [nueva])
    return _completar(nueva)


def eliminar(comunidad_id: str) -> bool:
    """Quita la comunidad de la lista (sus mensajes leídos quedan en disco y en el bucket)."""
    with _bloqueo:
        lista = _guardadas()
        restantes = [c for c in lista if c["id"] != comunidad_id]
        if len(restantes) == len(lista):
            return False
        _escribir(restantes)
    return True
