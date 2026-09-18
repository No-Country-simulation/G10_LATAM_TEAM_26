"""
CommunityLab — Bot de Discord para captura de conversaciones.

Dos modos de uso:
  1. LIVE:     escucha los canales en tiempo real y guarda cada mensaje.
  2. BACKFILL: descarga el historial existente de los canales al arrancar.

Los mensajes se guardan en data/raw/ como JSON Lines (un mensaje por línea),
en formato crudo compatible con el adaptador de ingesta (Formato A).

Requisitos:
    pip install discord.py python-dotenv

Configuración (.env en la raíz del proyecto):
    DISCORD_BOT_TOKEN=tu-token-aqui
    SERVIDORES_OBSERVADOS=      # nombres de servidores, separados por coma (vacío = todos)
    CANALES_OBSERVADOS=         # nombres de canales, separados por coma (vacío = todos)
    MODO_BACKFILL=true          # true = descarga historial al arrancar
    BACKFILL_LIMITE=500         # máx. de mensajes por canal en el backfill

Ejecución:
    python -m ingesta.discord_bot
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import discord
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CANALES_OBSERVADOS = {
    c.strip().lower()
    for c in os.environ.get("CANALES_OBSERVADOS", "").split(",")
    if c.strip()
}
SERVIDORES_OBSERVADOS = {
    s.strip().lower()
    for s in os.environ.get("SERVIDORES_OBSERVADOS", "").split(",")
    if s.strip()
}
MODO_BACKFILL = os.environ.get("MODO_BACKFILL", "false").lower() == "true"
BACKFILL_LIMITE = int(os.environ.get("BACKFILL_LIMITE", "500"))

_BASE = Path(__file__).resolve().parent.parent
RAW_DIR = _BASE / "data" / "raw"
CONFIG_DIR = _BASE / "data" / "config"
TOPOLOGIA_PATH = CONFIG_DIR / "discord_topologia.json"   # la escribe el bot
CAPTURA_CONFIG_PATH = CONFIG_DIR / "captura_config.json"  # la escribe el panel

# Cache de la config dinámica: se relee solo cuando el archivo cambia
_config_cache: dict = {"mtime": None, "canales": None}

intents = discord.Intents.default()
intents.message_content = True  # requiere activar el intent en el Developer Portal

client = discord.Client(intents=intents)


def _config_dinamica() -> set[str] | None:
    """Lee los canales elegidos desde el panel (captura_config.json).

    Devuelve un set de claves "servidor/canal" en minúsculas, o None si el
    archivo no existe (en ese caso rigen las variables de entorno).
    Se cachea por mtime: cambiar el archivo aplica en caliente, sin reiniciar.
    """
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
        print(f"🔄 Config de captura recargada: {len(_config_cache['canales'])} canales activos")
    return _config_cache["canales"]


def _escribir_topologia(guilds: list[discord.Guild]) -> None:
    """Publica qué servidores/canales ve el bot, para que el panel los liste."""
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
    TOPOLOGIA_PATH.write_text(
        json.dumps(topo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"🗺️  Topología publicada en {TOPOLOGIA_PATH}")


def _servidor_observado(guild: discord.Guild | None) -> bool:
    """Sin lista configurada se observan todos los servidores."""
    if guild is None:
        return False
    if not SERVIDORES_OBSERVADOS:
        return True
    return guild.name.lower() in SERVIDORES_OBSERVADOS


def _canal_observado(channel: discord.abc.GuildChannel) -> bool:
    """Prioridad: config del panel (captura_config.json) > variables de entorno.

    Sin config del panel ni variables, se observa todo.
    """
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
    """Serializa el mensaje COMPLETO, sin filtros ni destilación.

    Capa raw (bronze): se guarda todo tal como llegó — incluidos mensajes
    de bots, mensajes cortos y campos que hoy no usamos. La limpieza,
    el filtrado y la anonimización son responsabilidad de la fase
    siguiente (adaptador de ingesta → Formato A), nunca de la captura.
    """
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
    print(f"✅ Bot conectado como {client.user}")
    _escribir_topologia(list(client.guilds))
    if not MODO_BACKFILL:
        print("👂 Modo LIVE: escuchando mensajes nuevos...")
        return
    print(f"⏬ Backfill: descargando hasta {BACKFILL_LIMITE} mensajes por canal...")
    total = 0
    for guild in client.guilds:
        for channel in guild.text_channels:
            if not _canal_observado(channel):
                continue
            permisos = channel.permissions_for(guild.me)
            if not (permisos.view_channel and permisos.read_message_history):
                print(f"   ⚠️  Sin permisos en #{channel.name}, salteado")
                continue
            n = await _backfill_canal(channel)
            total += n
            print(f"   #{channel.name}: {n} mensajes")
    print(f"⏬ Backfill terminado: {total} mensajes en {_ruta_salida()}")
    print("👂 Quedo escuchando mensajes nuevos (Ctrl+C para salir)...")


@client.event
async def on_message(message: discord.Message):
    if message.guild is None or not _canal_observado(message.channel):
        return
    if message.author.id == client.user.id:  # nunca capturar los mensajes propios
        return
    _guardar(_serializar_mensaje(message))
    origen = "🤖" if message.author.bot else "📩"
    print(f"{origen} [{message.channel.name}] {message.author.display_name}: {message.content[:60]}")


if __name__ == "__main__":
    client.run(TOKEN)
