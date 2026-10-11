"""
CommunityLab AI - Ingestion Loaders
Transforma archivos estáticos (fixtures) y capturas de Discord (.jsonl)
en entidades de dominio validadas por Pydantic (BatchInputPayload).
"""
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from src.domain.schemas import BatchInputPayload, RawMessageInteraction
from src.utils.logger import setup_logger

logger = setup_logger("ingestion_loaders")

Lote = Tuple[List[Dict[str, Any]], Dict[str, Any]]


def interacciones_desde_payload(payload: BatchInputPayload, limite: Optional[int] = None) -> Lote:
    """Convierte un lote validado (Formato A) en la lista de mensajes que recibe el motor."""
    interacciones = [{
        "message_id": m.message_id,
        "texto": m.texto,
        "canal": m.channel,
        "fecha": m.timestamp,
        "autor": m.autor,
        "source": m.source,
        "reacciones": m.metadata.get("reacciones", 0),
        "respuestas": m.metadata.get("respuestas", 0),
    } for m in payload.interacciones[:limite]]
    metadatos = {"origen_comunidad": payload.origen_comunidad, "periodo_referencia": payload.periodo_referencia}
    return interacciones, metadatos


def _limpiar_discord(texto: str) -> str:
    """Reemplaza menciones de Discord (<@id>, <@&id>, <#id>) para no enviar IDs al LLM."""
    texto = re.sub(r"<@&\d+>", "@rol", texto)
    texto = re.sub(r"<@!?\d+>", "@usuario", texto)
    return re.sub(r"<#\d+>", "#canal", texto).strip()


def _normalizar_fila(fila: Dict[str, str], indice: int) -> Dict[str, Any]:
    if "texto" in fila:  # CSV simple: message_id, texto
        return {"message_id": fila.get("message_id") or f"csv-{indice:04d}", "texto": (fila["texto"] or "").strip()}
    # Export de Discord: AuthorID, Author, Date, Content, Attachments, Reactions
    return {
        "message_id": f"discord-{indice:04d}",
        "texto": _limpiar_discord(fila.get("Content") or ""),
        "fecha": (fila.get("Date") or "")[:19],
        "autor": fila.get("Author"),
        "reacciones": sum(int(n) for n in re.findall(r"\((\d+)\)", fila.get("Reactions") or "")),
    }


def cargar_csv(ruta: str) -> Lote:
    """CSV con columnas message_id/texto o export de Discord; descarta filas sin texto."""
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        filas = [_normalizar_fila(fila, i) for i, fila in enumerate(csv.DictReader(f), start=1)]
    return [fila for fila in filas if fila["texto"]], {}


def cargar_json(ruta: str) -> Lote:
    """Lote JSON (Formato A) con la lista 'interacciones'."""
    with open(ruta, encoding="utf-8-sig") as f:
        datos = json.load(f)
    interacciones = []
    for i, item in enumerate(datos.get("interacciones", []), start=1):
        metadata = item.get("metadata") or {}
        interacciones.append({
            "message_id": item.get("message_id") or f"json-{i:04d}",
            "texto": (item.get("texto") or "").strip(),
            "canal": item.get("channel"),
            "fecha": item.get("timestamp"),
            "autor": item.get("autor"),
            "source": item.get("source", "discord"),
            "reacciones": metadata.get("reacciones", 0),
            "respuestas": metadata.get("respuestas", 0),
        })
    metadatos = {k: datos[k] for k in ("origen_comunidad", "periodo_referencia") if datos.get(k)}
    return [m for m in interacciones if m["texto"]], metadatos


def cargar_entrada(ruta: str) -> Lote:
    return cargar_json(ruta) if ruta.lower().endswith(".json") else cargar_csv(ruta)


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


def leer_capturas(raw_dir: str = "data/raw") -> List[Dict[str, Any]]:
    """Todos los mensajes guardados por el bot de Discord en data/raw/ (un .jsonl por día)."""
    registros = []
    for archivo in sorted(Path(raw_dir).glob("**/*discord_capturas.jsonl")):
        with open(archivo, "r", encoding="utf-8") as f:
            for linea in f:
                try:
                    registros.append(json.loads(linea))
                except json.JSONDecodeError:
                    continue
    return registros


def _tipo_por_canal(canal: str) -> str:
    """Clasificación heurística inicial basada en el canal de origen."""
    if "logro" in canal or "empleo" in canal:
        return "testimonio"
    if "duda" in canal or "pregunt" in canal:
        return "pregunta_tecnica"
    if "feedback" in canal:
        return "feedback"
    return "conversacion"


def payload_desde_discord(registros: List[Dict[str, Any]],
                          origen: str = "Discord_Servidor_Oficial") -> Optional[BatchInputPayload]:
    """Normaliza mensajes de Discord (del bot o de la API) al Formato A: sin bots ni mensajes vacíos, sin repetidos
    (gana la última captura, que trae las ediciones) y del más reciente al más antiguo, para que los primeros N
    mensajes del lote sean los últimos que llegaron."""
    unicos: Dict[str, Dict[str, Any]] = {}
    for registro in registros:
        if registro.get("id") and not registro.get("author", {}).get("bot", False):
            unicos[registro["id"]] = registro
    interacciones: List[RawMessageInteraction] = []
    for raw_msg in sorted(unicos.values(), key=lambda r: r.get("timestamp", ""), reverse=True):
        content = _limpiar_discord(raw_msg.get("clean_content") or raw_msg.get("content", ""))
        if not content:
            continue
        canal = (raw_msg.get("channel") or {}).get("name") or "general"
        interacciones.append(RawMessageInteraction(
            message_id=f"DISC-{raw_msg['id'][-6:]}",
            source="discord_live",
            channel=canal.lower(),
            timestamp=raw_msg.get("timestamp", ""),
            autor=raw_msg.get("author", {}).get("display_name") or "Miembro Discord",
            tipo_declarado=_tipo_por_canal(canal.lower()),
            texto=content,
            metadata={
                "reacciones": sum(r.get("count", 0) for r in raw_msg.get("reactions", [])),
                "respuestas": 0,
                "attachments": len(raw_msg.get("attachments", [])),
            },
        ))
    if not interacciones:
        return None
    return BatchInputPayload(
        formato_version="1.0-live",
        origen_comunidad=origen,
        periodo_referencia="Capturas_En_Vivo",
        interacciones=interacciones,
    )


def load_discord_raw_stream(raw_dir: str = "data/raw", recientes: Optional[List[Dict[str, Any]]] = None,
                            origen: str = "Discord_Servidor_Oficial") -> Optional[BatchInputPayload]:
    """Mensajes de Discord guardados en `raw_dir` más los traídos bajo demanda con la API (si los hay)."""
    return payload_desde_discord(leer_capturas(raw_dir) + list(recientes or []), origen)


def load_uploaded_json_file(archivo) -> BatchInputPayload:
    """Lote JSON (Formato A) subido desde el panel. Lanza ValueError con un mensaje legible si no es válido.
    Basado en la carga de archivos de Álvaro."""
    try:
        datos = json.load(archivo)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(f"El archivo no es un JSON válido ({error})") from error
    if not isinstance(datos, dict) or "interacciones" not in datos:
        raise ValueError("Falta la lista 'interacciones' del Formato A (ver spec.md)")
    try:
        return BatchInputPayload(**datos)
    except Exception as error:
        raise ValueError(f"El lote no cumple el Formato A: {str(error).splitlines()[0]}") from error
