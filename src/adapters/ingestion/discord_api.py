"""
CommunityLab AI - Ingesta de Discord bajo demanda (API REST)
Lee los mensajes de los canales cuando el panel los pide, sin un bot conectado todo el tiempo. Usa el token de la
aplicación de Discord (DISCORD_BOT_TOKEN), que debe estar en el servidor con permiso de leer el historial y con el
intent MESSAGE CONTENT activo en el Developer Portal.

Lectura incremental: la primera vez trae los últimos DISCORD_LIMITE_POR_CANAL mensajes de cada canal; después,
solo los posteriores al último leído (parámetro `after`), así no se salta mensajes aunque hayan llegado más de 100.
Incluye los hilos activos y los archivados recientes. Lo leído se acumula en data/raw/discord/ y el loader lo
normaliza al Formato A junto con cualquier captura anterior.

Con OCI conectado, cada lectura con mensajes nuevos se sube también al bucket (raw/YYYY-MM-DD/discord_*.jsonl), y un
servidor nuevo con el disco vacío recupera desde ahí todo lo leído antes: lo capturado no depende de un disco.
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Tuple

import requests

from src import config
from src.utils.logger import setup_logger

logger = setup_logger("discord_api")

API = "https://discord.com/api/v10"
TIPOS_CANAL_TEXTO = (0, 5)  # texto y anuncios
TIPOS_HILO = (10, 11, 12)  # hilos de anuncios, públicos y privados
TIPOS_MENSAJE = (0, 19)  # mensaje normal y respuesta; el resto son avisos del sistema (uniones, fijados, hilos…)
LIMITE_POR_CANAL = int(os.getenv("DISCORD_LIMITE_POR_CANAL", "100"))
MAXIMO_NUEVOS = 1000  # tope por canal en una lectura incremental
CARPETA = config.RAIZ / "data" / "raw" / "discord"


def _nombres(variable: str) -> set:
    return {v.strip().lower() for v in os.getenv(variable, "").split(",") if v.strip()}


class DiscordAPI:
    def __init__(self, token: Optional[str] = None, sesion=None, servidor_id: Optional[str] = None):
        self.token = (token if token is not None else os.getenv("DISCORD_BOT_TOKEN", "")).strip()
        self.sesion = sesion or requests.Session()
        self.servidor_id = servidor_id  # si se indica, solo se lee ese servidor

    def identidad(self) -> Dict[str, Any]:
        """Nombre de la aplicación y servidores a los que tiene acceso. Lanza error si el token no es válido."""
        r = self.sesion.get(f"{API}/users/@me", timeout=15, headers={"Authorization": f"Bot {self.token}"})
        if r.status_code == 401:
            raise PermissionError("El token no es válido o fue revocado.")
        r.raise_for_status()
        app = r.json()
        servidores = [{"id": g["id"], "nombre": g["name"]} for g in self._get("/users/@me/guilds") or []]
        return {"aplicacion": app.get("global_name") or app.get("username"), "servidores": servidores}

    @property
    def configurado(self) -> bool:
        return bool(self.token) and not self.token.startswith("pega-tu")

    def _get(self, ruta: str, params: Optional[Dict] = None) -> Any:
        """GET con el token; respeta el límite de Discord (429) una vez. None si no hay acceso (403/404)."""
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

    # ─── Canales e hilos ─────────────────────────────────────────────────────

    def canales(self) -> List[Dict[str, Any]]:
        """Canales de texto observados y sus hilos (activos y archivados recientes). Cada hilo lleva el nombre de su
        canal padre, que es el que se usa como canal del mensaje."""
        servidores, observados = _nombres("SERVIDORES_OBSERVADOS"), _nombres("CANALES_OBSERVADOS")
        elegidos = []
        for guild in self._get("/users/@me/guilds") or []:
            if (servidores and guild["name"].lower() not in servidores) or \
                    (self.servidor_id and guild["id"] != self.servidor_id):
                continue
            g = {"id": guild["id"], "name": guild["name"]}
            texto = {c["id"]: c for c in self._get(f"/guilds/{guild['id']}/channels") or []
                     if c["type"] in TIPOS_CANAL_TEXTO and (not observados or c["name"].lower() in observados)}
            elegidos += [{"guild": g, "id": c["id"], "name": c["name"], "hilo": None} for c in texto.values()]
            hilos = list((self._get(f"/guilds/{guild['id']}/threads/active") or {}).get("threads", []))
            with ThreadPoolExecutor(max_workers=4) as pool:
                for archivados in pool.map(
                        lambda cid: (self._get(f"/channels/{cid}/threads/archived/public", {"limit": 20}) or {}),
                        list(texto)):
                    hilos += archivados.get("threads", [])
            vistos = set()
            for h in hilos:
                padre = texto.get(h.get("parent_id"))
                if padre and h["type"] in TIPOS_HILO and h["id"] not in vistos:
                    vistos.add(h["id"])
                    elegidos.append({"guild": g, "id": h["id"], "name": padre["name"], "hilo": h.get("name")})
        return elegidos

    # ─── Mensajes ────────────────────────────────────────────────────────────

    def _paginas(self, canal: Dict[str, Any], limite: int, despues: Optional[str]) -> List[Dict[str, Any]]:
        """Sin `despues`: los últimos `limite` mensajes. Con `despues`: todos los posteriores (hasta MAXIMO_NUEVOS)."""
        mensajes: List[Dict[str, Any]] = []
        cursor = despues
        while True:
            params: Dict[str, Any] = {"limit": 100}
            if despues:
                params["after"] = cursor
            else:
                params["limit"] = min(100, limite - len(mensajes))
                if mensajes:
                    params["before"] = mensajes[-1]["id"]
            pagina = self._get(f"/channels/{canal['id']}/messages", params)
            if not pagina:  # sin permiso de lectura o sin más mensajes
                break
            mensajes.extend(pagina)
            if despues:
                cursor = max(pagina, key=lambda m: int(m["id"]))["id"]
            if len(pagina) < params["limit"] or len(mensajes) >= (MAXIMO_NUEVOS if despues else limite):
                break
        return mensajes

    def leer_canal(self, canal: Dict[str, Any], limite: int = LIMITE_POR_CANAL,
                   despues: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """(registros, id del último mensaje leído) de un canal o hilo."""
        crudos = self._paginas(canal, limite, despues)
        ultimo = max((m["id"] for m in crudos), key=int, default=despues)
        return [_registro(m, canal) for m in crudos if m.get("type", 0) in TIPOS_MENSAJE], ultimo

    def mensajes_recientes(self, limite_por_canal: int = LIMITE_POR_CANAL) -> List[Dict[str, Any]]:
        """Los últimos `limite_por_canal` mensajes de cada canal e hilo observado (lectura completa, sin cursores)."""
        if not self.configurado:
            return []
        canales = self.canales()
        with ThreadPoolExecutor(max_workers=4) as pool:
            leidos = list(pool.map(lambda c: self.leer_canal(c, limite_por_canal)[0], canales))
        return [r for lista in leidos for r in lista]

    def sincronizar(self, carpeta: Path = CARPETA, almacen: Any = None, prefijo: str = "discord") -> Dict[str, Any]:
        """Lectura incremental: agrega a carpeta/discord_capturas.jsonl solo lo nuevo de cada canal desde la última
        lectura (cursores.json) y devuelve un resumen. `almacen` (ObjectStorageAdapter conectado, opcional) recibe
        una copia de lo nuevo en raw/ y sirve para recuperar lo leído si el disco está vacío."""
        if not self.configurado:
            return {"nuevos": 0, "canales": 0}
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo_cursores = carpeta / "cursores.json"
        recuperados = 0
        archivo, marca = carpeta / "discord_capturas.jsonl", carpeta / ".en_oci"
        if almacen is not None and not archivo.exists():
            recuperados = _recuperar(almacen, carpeta, prefijo)
            marca.touch()
        elif almacen is not None and not marca.exists():  # lo leído antes de conectar OCI se sube una sola vez
            if archivo.stat().st_size and _subir(almacen, archivo.read_bytes(), "inicial", prefijo):
                marca.touch()
        try:
            cursores = json.loads(archivo_cursores.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            cursores = {}
        canales = self.canales()
        with ThreadPoolExecutor(max_workers=4) as pool:
            leidos = list(pool.map(lambda c: (c["id"], *self.leer_canal(c, despues=cursores.get(c["id"]))), canales))
        lineas = []
        for canal_id, registros, ultimo in leidos:
            lineas += [json.dumps(r, ensure_ascii=False) for r in registros]
            if ultimo:
                cursores[canal_id] = ultimo
        if lineas:
            with (carpeta / "discord_capturas.jsonl").open("a", encoding="utf-8") as salida:
                salida.write("\n".join(lineas) + "\n")
        temporal = archivo_cursores.with_suffix(".tmp")
        temporal.write_text(json.dumps(cursores, indent=1), encoding="utf-8")
        temporal.replace(archivo_cursores)
        en_oci = None
        if almacen is not None and lineas:
            en_oci = _subir(almacen, ("\n".join(lineas) + "\n").encode("utf-8"), str(len(lineas)), prefijo)
        logger.info(f"Discord: {len(lineas)} mensajes nuevos de {len(canales)} canales e hilos"
                    + (f", copia en {en_oci}" if en_oci else ""))
        return {"nuevos": len(lineas), "canales": len(canales), "en_oci": en_oci, "recuperados": recuperados}


def _subir(almacen: Any, datos: bytes, sufijo: str, prefijo: str = "discord") -> Optional[str]:
    """Copia en raw/YYYY-MM-DD/ del bucket. Si OCI no responde, lo leído sigue en el disco local."""
    ahora = datetime.now(timezone.utc)
    ruta = f"raw/{ahora:%Y-%m-%d}/{prefijo}_{ahora:%H%M%S}_{sufijo}.jsonl"
    try:
        almacen.subir(ruta, datos, "application/x-ndjson")
        return ruta
    except Exception as error:
        logger.warning(f"No se pudo subir a OCI la lectura de Discord ({type(error).__name__}: {error})")
        return None


def _recuperar(almacen: Any, carpeta: Path, prefijo: str = "discord") -> int:
    """Disco vacío: reconstruye discord_capturas.jsonl y los cursores con lo que ya se subió al bucket (raw/)."""
    try:
        nombres = sorted(n for n in almacen.listar("raw/") if PurePosixPath(n).name.startswith(f"{prefijo}_"))
        registros = []
        for nombre in nombres:
            registros += [json.loads(l) for l in almacen.leer(nombre).decode("utf-8").splitlines() if l.strip()]
    except Exception as error:
        logger.warning(f"No se pudo recuperar Discord desde OCI ({type(error).__name__}: {error})")
        return 0
    if not registros:
        return 0
    cursores: Dict[str, str] = {}
    for r in registros:
        canal = (r.get("channel") or {}).get("id")
        if canal and int(r["id"]) > int(cursores.get(canal, "0")):
            cursores[canal] = r["id"]
    with (carpeta / "discord_capturas.jsonl").open("w", encoding="utf-8") as salida:
        salida.write("\n".join(json.dumps(r, ensure_ascii=False) for r in registros) + "\n")
    (carpeta / "cursores.json").write_text(json.dumps(cursores, indent=1), encoding="utf-8")
    logger.info(f"Discord: {len(registros)} mensajes recuperados de OCI ({len(nombres)} archivos)")
    return len(registros)


def _texto_limpio(mensaje: Dict[str, Any]) -> str:
    """Las menciones a personas se ven con su nombre y no con su id; los emojis propios, por su nombre."""
    texto = mensaje.get("content") or ""
    for usuario in mensaje.get("mentions", []):
        nombre = usuario.get("global_name") or usuario.get("username") or "usuario"
        texto = re.sub(rf"<@!?{usuario['id']}>", f"@{nombre}", texto)
    return re.sub(r"<a?(:\w+:)\d+>", r"\1", texto)


def _registro(mensaje: Dict[str, Any], canal: Dict[str, Any]) -> Dict[str, Any]:
    autor = mensaje.get("author", {})
    return {
        "id": mensaje["id"],
        "guild": canal["guild"],
        "channel": {"id": canal["id"], "name": canal["name"], "hilo": canal.get("hilo")},
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
