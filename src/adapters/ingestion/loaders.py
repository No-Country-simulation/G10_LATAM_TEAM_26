"""
CommunityLab AI - Ingestion Loaders
Transforma archivos estáticos (fixtures) y capturas de Discord (.jsonl)
en entidades de dominio validadas por Pydantic (BatchInputPayload).
"""
import json
from pathlib import Path
from typing import List, Optional
from src.domain.schemas import BatchInputPayload, RawMessageInteraction
from src.utils.logger import setup_logger

logger = setup_logger("ingestion_loaders")


def load_fixture_data(file_path: str = "data/fixtures/lote_ejemplo_formato_a.json") -> Optional[BatchInputPayload]:
    """Carga y valida el lote de datos simulado (Formato A)."""
    path = Path(file_path)
    if not path.exists():
        logger.error(f"No existe el archivo fixture en: {file_path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return BatchInputPayload(**data)
    except Exception as e:
        logger.error(f"Error parseando el fixture {file_path}: {str(e)}")
        return None


def load_discord_raw_stream(raw_dir: str = "data/raw") -> Optional[BatchInputPayload]:
    """
    Lee las capturas en bruto (.jsonl) generadas por el bot de Discord en data/raw/,
    aplica filtrado inicial y normaliza los mensajes al contrato BatchInputPayload.
    """
    raw_path = Path(raw_dir)
    if not raw_path.exists():
        return None

    # Buscar todos los archivos .jsonl recursivamente
    jsonl_files = list(raw_path.glob("**/*discord_capturas.jsonl"))
    if not jsonl_files:
        return None

    # Tomar el más reciente por fecha de modificación
    latest_file = max(jsonl_files, key=lambda f: f.stat().st_mtime)
    logger.info(f"Cargando stream de Discord desde: {latest_file}")

    interacciones: List[RawMessageInteraction] = []

    with open(latest_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw_msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Descartar mensajes de bots
            if raw_msg.get("author", {}).get("bot", False):
                continue

            content = raw_msg.get("clean_content") or raw_msg.get("content", "")
            if not content.strip():
                continue

            channel_name = raw_msg.get("channel", {}).get("name", "general").lower()
            
            # Clasificación heurística inicial basada en el canal de origen
            tipo_declarado = "conversacion"
            if "logro" in channel_name or "empleo" in channel_name:
                tipo_declarado = "testimonio"
            elif "duda" in channel_name or "pregunt" in channel_name:
                tipo_declarado = "pregunta_tecnica"
            elif "feedback" in channel_name:
                tipo_declarado = "feedback"

            # Sumar conteo de reacciones del mensaje
            total_reacciones = sum(r.get("count", 0) for r in raw_msg.get("reactions", []))

            interacciones.append(
                RawMessageInteraction(
                    message_id=f"DISC-{raw_msg['id'][-6:]}",
                    source="discord_live",
                    channel=channel_name,
                    timestamp=raw_msg.get("timestamp", ""),
                    autor=raw_msg.get("author", {}).get("display_name", "Miembro Discord"),
                    tipo_declarado=tipo_declarado,
                    texto=content,
                    metadata={
                        "reacciones": total_reacciones,
                        "respuestas": 0,
                        "attachments": len(raw_msg.get("attachments", []))
                    }
                )
            )

    if not interacciones:
        return None

    return BatchInputPayload(
        formato_version="1.0-live",
        origen_comunidad="Discord_Servidor_Oficial",
        periodo_referencia="Capturas_En_Vivo",
        interacciones=interacciones
    )