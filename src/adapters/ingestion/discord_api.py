"""
CommunityLab AI - Ingesta de Discord bajo demanda (API REST)
Trae los mensajes recientes de los canales en el momento en que el panel los pide, sin mantener un bot conectado:
sirve igual en local y en Streamlit Cloud. Usa el mismo token del bot (DISCORD_BOT_TOKEN), que debe estar en el
servidor con permiso de leer el historial y con el intent MESSAGE CONTENT activo en el Developer Portal.

Devuelve registros con la misma forma que guarda el bot (discord_bot.py), para normalizarlos con el mismo loader.
"""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from src.utils.logger import setup_logger

logger = setup_logger("discord_api")

API = "https://discord.com/api/v10"
TIPOS_CANAL_TEXTO = (0, 5)  # texto y anuncios
TIPOS_MENSAJE = (0, 19)  # mensaje normal y respuesta; el resto son avisos del sistema (uniones, fijados…)
LIMITE_POR_CANAL = int(os.getenv("DISCORD_LIMITE_POR_CANAL", "100"))


def _nombres(variable: str) -> set:
    return {v.strip().lower() for v in os.getenv(variable, "").split(",") if v.strip()}


class DiscordAPI:
    def __init__(self, token: Optional[str] = None, sesion=None):
        self.token = (token if token is not None else os.getenv("DISCORD_BOT_TOKEN", "")).strip()
        self.sesion = sesion or requests.Session()

    @property
    def configurado(self) -> bool:
        return bool(self.token) and not self.token.startswith("pega-tu")

    def _get(self, ruta: str, params: Optional[Dict] = None) -> Any:
        """GET con el token del bot; respeta el límite de Discord (429) una vez. None si no hay acceso (403/404)."""
        for _ in range(2):
            r = self.sesion.get(f"{API}{ruta}", params=params, timeout=15,
                                headers={"Authorization": f"Bot {self.token}"})
            if r.status_code == 429:
                time.sleep(min(float(r.json().get("retry_after", 1)), 5))
                continue
            if r.status_code in (403, 404):
                return None
            r.raise_for_status()
            return r.json()
        return None

    def _canales(self) -> List[Dict[str, Any]]:
        servidores, canales = _nombres("SERVIDORES_OBSERVADOS"), _nombres("CANALES_OBSERVADOS")
        elegidos = []
        for guild in self._get("/users/@me/guilds") or []:
            if servidores and guild["name"].lower() not in servidores:
                continue
            for canal in self._get(f"/guilds/{guild['id']}/channels") or []:
                if canal["type"] in TIPOS_CANAL_TEXTO and (not canales or canal["name"].lower() in canales):
                    elegidos.append({"guild": {"id": guild["id"], "name": guild["name"]}, **canal})
        return elegidos

    def _mensajes_canal(self, canal: Dict[str, Any], limite: int) -> List[Dict[str, Any]]:
        mensajes, antes = [], None
        while len(mensajes) < limite:
            params = {"limit": min(100, limite - len(mensajes))}
            if antes:
                params["before"] = antes
            pagina = self._get(f"/channels/{canal['id']}/messages", params)
            if not pagina:  # sin permiso de lectura o canal sin más historial
                break
            mensajes.extend(pagina)
            antes = pagina[-1]["id"]
            if len(pagina) < params["limit"]:
                break
        return [_registro(m, canal) for m in mensajes if m.get("type", 0) in TIPOS_MENSAJE]

    def mensajes_recientes(self, limite_por_canal: int = LIMITE_POR_CANAL) -> List[Dict[str, Any]]:
        """Los últimos `limite_por_canal` mensajes de cada canal de texto observado (sin orden garantizado)."""
        if not self.configurado:
            return []
        canales = self._canales()
        with ThreadPoolExecutor(max_workers=4) as hilos:
            por_canal = list(hilos.map(lambda c: self._mensajes_canal(c, limite_por_canal), canales))
        registros = [r for lista in por_canal for r in lista]
        logger.info(f"Discord: {len(registros)} mensajes de {len(canales)} canales")
        return registros


def _texto_limpio(mensaje: Dict[str, Any]) -> str:
    """Como clean_content del bot: las menciones a personas se ven con su nombre y no con su id."""
    texto = mensaje.get("content") or ""
    for usuario in mensaje.get("mentions", []):
        nombre = usuario.get("global_name") or usuario.get("username") or "usuario"
        texto = re.sub(rf"<@!?{usuario['id']}>", f"@{nombre}", texto)
    return re.sub(r"<a?(:\w+:)\d+>", r"\1", texto)  # emojis propios del servidor


def _registro(mensaje: Dict[str, Any], canal: Dict[str, Any]) -> Dict[str, Any]:
    autor = mensaje.get("author", {})
    return {
        "id": mensaje["id"],
        "guild": canal["guild"],
        "channel": {"id": canal["id"], "name": canal["name"]},
        "author": {"id": autor.get("id"), "username": autor.get("username"),
                   "display_name": autor.get("global_name") or autor.get("username"), "bot": autor.get("bot", False)},
        "content": mensaje.get("content", ""),
        "clean_content": _texto_limpio(mensaje),
        "timestamp": mensaje.get("timestamp", ""),
        "attachments": [{"filename": a.get("filename")} for a in mensaje.get("attachments", [])],
        "reactions": [{"emoji": (r.get("emoji") or {}).get("name"), "count": r.get("count", 0)}
                      for r in mensaje.get("reactions", [])],
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
