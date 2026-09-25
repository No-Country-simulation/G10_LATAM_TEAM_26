"""
CommunityLab AI - Empaquetador
Arma el paquete de distribución (Formato B) y el análisis por mensaje (Formato P) definidos en spec.md.
"""
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List

from src import config
from src.core.agents.detector import CLASIFICACION_NEUTRA
from src.core.estado import AgentState

NOMBRES_TIPO = {
    "SUCCESS_STORY": ("historia de éxito", "historias de éxito"),
    "LOGRO": ("logro", "logros"),
    "FAQ": ("pregunta técnica", "preguntas técnicas"),
    "CONSULTA_OPERATIVA": ("consulta operativa", "consultas operativas"),
    "OTRO": ("mensaje general", "mensajes generales"),
}


def _tendencias(analizados: List[Dict[str, Any]], clasificaciones: Dict[str, Dict[str, Any]],
                periodo: str) -> List[Dict[str, Any]]:
    """Temas sustantivos con 2 o más menciones, con el desglose por tipo de mensaje."""
    por_tema: Dict[str, Counter] = {}
    for m in analizados:
        tipo = clasificaciones.get(m["message_id"], {}).get("type", "OTRO")
        for tema in set(m["topics"]) - {config.TEMA_SOCIAL}:
            por_tema.setdefault(tema, Counter())[tipo] += 1
    tendencias = []
    for tema, tipos in sorted(por_tema.items(), key=lambda kv: -sum(kv[1].values()))[:5]:
        menciones = sum(tipos.values())
        if menciones < 2:
            continue
        detalle = ", ".join(f"{n} {NOMBRES_TIPO[t][0 if n == 1 else 1]}" for t, n in tipos.most_common())
        tendencias.append({
            "tema": tema,
            "menciones": menciones,
            "descripcion": f"{menciones} mensajes sobre {tema} en {periodo.replace('_', ' ').lower()} ({detalle})",
        })
    return tendencias


def avisos(state: AgentState) -> Dict[str, List[str]]:
    """Lo que no se completó en la corrida: mensajes sin análisis o sin clasificación y piezas sin redactar."""
    return {
        "sin_analisis": [m["message_id"] for m in state.get("mensajes_analizados", []) if not m.get("analisis_ok")],
        "sin_clasificacion": [mid for mid, c in state.get("clasificaciones", {}).items()
                              if c.get("reason") == CLASIFICACION_NEUTRA["reason"]],
        "piezas_pendientes": list(state.get("piezas_pendientes", [])),
    }


def empaquetar(state: AgentState):
    """Nodo 4 del grafo: resumen, tendencias y activos en el paquete final (Formato B)."""
    analizados = state.get("mensajes_analizados", [])
    clasificaciones = state.get("clasificaciones", {})
    metadatos = state.get("metadatos_lote", {})
    ahora = datetime.now(timezone.utc)
    anio, semana_iso, _ = ahora.isocalendar()
    periodo = metadatos.get("periodo_referencia") or f"Semana_{semana_iso:02d}"
    numero_semana = int(re.search(r"\d+", periodo).group()) if re.search(r"\d+", periodo) else semana_iso
    # id por timestamp: único sin leer el disco, así procesar() no tiene efectos secundarios
    paquete_id = f"PKG-{anio}-S{numero_semana:02d}-{ahora.strftime('%H%M%S')}"

    sentimiento = Counter(m["sentiment"] for m in analizados)
    temas = Counter(t for m in analizados for t in m["topics"] if t != config.TEMA_SOCIAL)
    incompleto = any(avisos(state).values())

    paquete_final = {
        "formato_version": "1.0",
        "status": "parcial" if incompleto else "exito",
        "paquete_id": paquete_id,
        "origen_comunidad": metadatos.get("origen_comunidad", "desconocido"),
        "periodo_referencia": periodo,
        "fecha_generacion": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "resumen_comunidad": {
            "total_interacciones_procesadas": len(state["interacciones_originales"]),
            "sentimiento_predominante": sentimiento.most_common(1)[0][0] if sentimiento else None,
            "distribucion_sentimiento": {s: sentimiento.get(s, 0) for s in ("positive", "neutral", "negative")},
            "temas_principales": [t for t, _ in temas.most_common(5)],
            "oportunidades_detectadas": len(state.get("oportunidades", [])),
            "consultas_operativas": sum(1 for c in clasificaciones.values() if c["type"] == "CONSULTA_OPERATIVA"),
            "tendencias_detectadas": _tendencias(analizados, clasificaciones, periodo),
        },
        "activos": state.get("activos_generados", []),
        "almacenamiento_oci": {
            "bucket": config.BUCKET_OCI,
            "ruta_objeto": f"generated/{ahora:%Y-%m-%d}/{paquete_id}.json",
            "status": "pendiente",
        },
    }
    return {"paquete_final": paquete_final}


def formato_p(state: AgentState) -> List[Dict[str, Any]]:
    """Análisis por mensaje (Formato P): tracking, analysis y opportunity, en el orden del lote."""
    clasificaciones = state.get("clasificaciones", {})
    opp_ids = {o["message_id"]: o["opportunity_id"] for o in state.get("oportunidades", [])}
    procesados = []
    for m in state.get("mensajes_analizados", []):
        c = clasificaciones.get(m["message_id"], CLASIFICACION_NEUTRA)
        procesados.append({
            "tracking": {"message_id": m["message_id"], "source": m.get("source", "discord"),
                         "channel": m.get("canal"), "timestamp": m.get("fecha")},
            "analysis": {"sentiment": m["sentiment"], "topics": m["topics"], "intent": m.get("intencion", ""),
                         "relevance_score": c["score"]},
            "opportunity": {"opportunity_id": opp_ids.get(m["message_id"]), "type": c["type"],
                            "opportunity_score": c["score"], "reason": c["reason"]},
        })
    return procesados
