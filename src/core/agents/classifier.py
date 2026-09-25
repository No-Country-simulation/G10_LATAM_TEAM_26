"""
Agente 1+2 compacto: Community Classifier
Una llamada por lote en lugar de dos: sentimiento, temas y tipo para todos los mensajes, y score con razón
solo para los candidatos a contenido. El umbral por tipo lo sigue aplicando el código (detector.es_oportunidad).
"""
from src import config
from src.adapters.llm.proveedores import invocar_lotes
from src.core.agents import simulado
from src.core.agents.detector import CLASIFICACION_NEUTRA, es_oportunidad
from src.core.agents.esquemas_llm import ClasificacionCompacta
from src.core.estado import AgentState
from src.core.prompts import PROMPT_CLASIFICADOR
from src.utils.texto import json_mensajes, lotes, texto_llm

TIPOS_CON_CONTENIDO = set(config.UMBRALES_POR_TIPO)


def _sin_candidatura(tipo: str) -> dict:
    """Clasificación de un mensaje que el modelo no propuso como candidato (queda bajo cualquier umbral)."""
    if tipo in TIPOS_CON_CONTENIDO:
        return {"type": tipo, "score": 0.3, "reason": "el modelo no lo propuso como candidato a contenido"}
    return {"type": tipo, "score": 0.1, "reason": "sin valor para contenido público según su tipo"}


def community_classifier(state: AgentState):
    """Nodo de clasificación compacta del grafo."""
    analizados, clasificaciones, oportunidades = [], {}, []
    campos = ["message_id", "texto", "canal", "reacciones", "respuestas"]
    bloques = list(lotes(state["interacciones_originales"]))
    resultados = [None] * len(bloques) if state.get("simulado") else invocar_lotes(
        PROMPT_CLASIFICADOR, ClasificacionCompacta, "analisis", 0,
        [{"mensajes": json_mensajes(lote, campos)} for lote in bloques])
    for lote, resultado in zip(bloques, resultados):
        breves = {m.message_id: m for m in (resultado.mensajes if resultado else [])}
        candidatos = {c.message_id: c for c in (resultado.candidatos if resultado else [])}
        for msg in lote:
            mid = msg["message_id"]
            if state.get("simulado"):
                analizados.append({**msg, **simulado.analisis(msg)})
                clasificaciones[mid] = simulado.clasificacion(msg)
            else:
                b, c = breves.get(mid), candidatos.get(mid)
                analizados.append({
                    **msg,
                    "sentiment": b.sentiment if b else "neutral",
                    "topics": [texto_llm(t).lower() for t in b.topics] if b else [],
                    "intencion": "",
                    "analisis_ok": b is not None,
                })
                if not b:
                    clasificaciones[mid] = dict(CLASIFICACION_NEUTRA)
                elif c and b.type in TIPOS_CON_CONTENIDO:
                    clasificaciones[mid] = {"type": b.type, "score": round(c.score, 2), "reason": texto_llm(c.reason)}
                else:
                    clasificaciones[mid] = _sin_candidatura(b.type)
            if es_oportunidad(clasificaciones[mid]):
                oportunidades.append({**analizados[-1], **clasificaciones[mid],
                                      "opportunity_id": f"OPP-{len(oportunidades) + 1:03d}"})
    return {"mensajes_analizados": analizados, "clasificaciones": clasificaciones, "oportunidades": oportunidades}
