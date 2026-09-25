"""
CommunityLab AI — Adaptador de Ingesta en Tiempo Real: Bot de Discord.
Reside formalmente en: src/adapters/ingestion/discord_bot.py

Modos:
  1. LIVE: Escucha eventos on_message y persiste en JSONL.
  2. BACKFILL: Descarga historial previo al arrancar.

Ejecución estándar:
  python -m src.adapters.ingestion.discord_bot
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import discord
from dotenv import load_dotenv

from src.utils.logger import setup_logger

logger = setup_logger("discord_bot")
load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
if not TOKEN:
    logger.error("Falta DISCORD_BOT_TOKEN en el archivo .env")

CANALES_OBSERVADOS = {
    c.strip().lower()
    for c in os.getenv("CANALES_OBSERVADOS", "").split(",")
    if c.strip()
}
SERVIDORES_OBSERVADOS = {
    s.strip().lower()
    for s in os.getenv("SERVIDORES_OBSERVADOS", "").split(",")
    if s.strip()
}
MODO_BACKFILL = os.getenv("MODO_BACKFILL", "false").lower() == "true"
BACKFILL_LIMITE = int(os.getenv("BACKFILL_LIMITE", "500"))

# Ruta absoluta calculada a la raíz del repositorio
_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = _ROOT / "data" / "raw"
CONFIG_DIR = _ROOT / "data" / "config"
TOPOLOGIA_PATH = CONFIG_DIR / "discord_topologia.json"
CAPTURA_CONFIG_PATH = CONFIG_DIR / "captura_config.json"

_config_cache: dict = {"mtime": None, "canales": None}

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)


def _config_dinamica() -> set[str] | None:
    try:
        mtime = CAPTURA_CONFIG_PATH.stat().st_mtime
    except FileNotFoundError:
        return None
    if _config_cache["mtime"] != mtime:
        data = json.loads(CAPTURA_CONFIG_PATH.read_text(encoding="utf-8"))
        _config_cache["canales"] = {
            f"{c['servidor'].lower()}/{c['canal'].lower()}"
            for c in data.get("canales_activos", [])
        }
        _config_cache["mtime"] = mtime
        logger.info(f"Config de captura recargada: {len(_config_cache['canales'])} canales activos")
    return _config_cache["canales"]


def _escribir_topologia(guilds: list[discord.Guild]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    topo = {
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "servidores": [
            {
                "servidor": g.name,
                "canales": [
                    {
                        "canal": ch.name,
                        "acceso_lectura": ch.permissions_for(g.me).view_channel
                        and ch.permissions_for(g.me).read_message_history,
                    }
                    for ch in g.text_channels
                ],
            }
            for g in guilds
        ],
    }
    TOPOLOGIA_PATH.write_text(json.dumps(topo, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Topología publicada en {TOPOLOGIA_PATH}")


def _servidor_observado(guild: discord.Guild | None) -> bool:
    if guild is None:
        return False
    if not SERVIDORES_OBSERVADOS:
        return True
    return guild.name.lower() in SERVIDORES_OBSERVADOS


def _canal_observado(channel: discord.abc.GuildChannel) -> bool:
    guild = getattr(channel, "guild", None)
    canales_panel = _config_dinamica()
    if canales_panel is not None:
        if guild is None:
            return False
        return f"{guild.name.lower()}/{channel.name.lower()}" in canales_panel
    if not _servidor_observado(guild):
        return False
    if not CANALES_OBSERVADOS:
        return True
    return channel.name.lower() in CANALES_OBSERVADOS


def _serializar_mensaje(msg: discord.Message) -> dict:
    return {
        "id": str(msg.id),
        "type": msg.type.name,
        "guild": {
            "id": str(msg.guild.id),
            "name": msg.guild.name,
        } if msg.guild else None,
        "channel": {
            "id": str(msg.channel.id),
            "name": getattr(msg.channel, "name", None),
            "category": getattr(getattr(msg.channel, "category", None), "name", None),
        },
        "author": {
            "id": str(msg.author.id),
            "username": msg.author.name,
            "display_name": msg.author.display_name,
            "bot": msg.author.bot,
        },
        "content": msg.content,
        "clean_content": msg.clean_content,
        "timestamp": msg.created_at.astimezone(timezone.utc).isoformat(),
        "edited_timestamp": msg.edited_at.astimezone(timezone.utc).isoformat() if msg.edited_at else None,
        "pinned": msg.pinned,
        "mentions": [str(u.id) for u in msg.mentions],
        "mention_everyone": msg.mention_everyone,
        "attachments": [
            {"filename": a.filename, "url": a.url, "content_type": a.content_type, "size": a.size}
            for a in msg.attachments
        ],
        "embeds_count": len(msg.embeds),
        "stickers": [s.name for s in msg.stickers],
        "reactions": [
            {"emoji": str(r.emoji), "count": r.count}
            for r in msg.reactions
        ],
        "reference_message_id": str(msg.reference.message_id) if msg.reference and msg.reference.message_id else None,
        "thread_id": str(msg.thread.id) if getattr(msg, "thread", None) else None,
        "jump_url": msg.jump_url,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }


def _ruta_salida() -> Path:
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    carpeta = RAW_DIR / hoy
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta / "discord_capturas.jsonl"


def _guardar(registro: dict) -> None:
    with _ruta_salida().open("a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


async def _backfill_canal(channel: discord.TextChannel) -> int:
    guardados = 0
    async for msg in channel.history(limit=BACKFILL_LIMITE, oldest_first=True):
        _guardar(_serializar_mensaje(msg))
        guardados += 1
    return guardados


@client.event
async def on_ready():
    logger.info(f"Bot conectado como {client.user}")
    _escribir_topologia(list(client.guilds))
    if not MODO_BACKFILL:
        logger.info("Modo LIVE: escuchando mensajes nuevos...")
        return
    logger.info(f"Backfill: descargando hasta {BACKFILL_LIMITE} mensajes por canal...")
    total = 0
    for guild in client.guilds:
        for channel in guild.text_channels:
            if not _canal_observado(channel):
                continue
            permisos = channel.permissions_for(guild.me)
            if not (permisos.view_channel and permisos.read_message_history):
                logger.warning(f"Sin permisos en #{channel.name}, omitido")
                continue
            n = await _backfill_canal(channel)
            total += n
            logger.info(f"#{channel.name}: {n} mensajes descargados")
    logger.info(f"Backfill completado: {total} mensajes en {_ruta_salida()}")
    logger.info("Escuchando mensajes nuevos (Ctrl+C para salir)...")


@client.event
async def on_message(message: discord.Message):
    if message.guild is None or not _canal_observado(message.channel):
        return
    if message.author.id == client.user.id:
        return
    _guardar(_serializar_mensaje(message))
    origen = "BOT" if message.author.bot else "USER"
    logger.info(f"[{origen}] [{message.channel.name}] {message.author.display_name}: {message.content[:60]}")


if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN no está definido en .env", file=sys.stderr)
        sys.exit(1)
    client.run(TOKEN)