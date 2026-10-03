"""
Agente 2: Opportunity Detector
Clasifica y puntúa cada mensaje con IA; las oportunidades se filtran por el umbral de su tipo.
"""
from src import config
from src.adapters.llm.proveedores import invocar_lotes
from src.core.agents import simulado
from src.core.agents.esquemas_llm import ClasificacionLote
from src.core.estado import AgentState
from src.core.prompts import PROMPT_DETECTOR
from src.utils.texto import json_mensajes, lotes, texto_llm

# Un mensaje que el modelo omite recibe esta clasificación explícita: nunca desaparece en silencio
CLASIFICACION_NEUTRA = {"type": "NONE", "score": 0.0,
                        "reason": "sin clasificar (el modelo omitió este id); revisar manualmente"}


def es_oportunidad(clasificacion: dict) -> bool:
    umbral = config.UMBRALES_POR_TIPO.get(clasificacion["type"])
    return umbral is not None and clasificacion["score"] >= umbral


def opportunity_detector(state: AgentState):
    """Nodo 2 del grafo."""
    clasificaciones = {}
    oportunidades = []
    campos = ["message_id", "texto", "canal", "reacciones", "respuestas", "sentiment", "topics", "intencion"]
    bloques = list(lotes(state["mensajes_analizados"]))
    resultados = [None] * len(bloques) if state.get("simulado") else invocar_lotes(
        PROMPT_DETECTOR, ClasificacionLote, "analisis", 0,
        [{"mensajes": json_mensajes(lote, campos)} for lote in bloques])
    for lote, resultado in zip(bloques, resultados):
        por_id = {c.message_id: c for c in (resultado.mensajes if resultado else [])}
        for msg in lote:
            if state.get("simulado"):
                clasificaciones[msg["message_id"]] = simulado.clasificacion(msg)
            else:
                c = por_id.get(msg["message_id"])
                clasificaciones[msg["message_id"]] = (
                    {"type": c.type, "score": round(c.score, 2), "reason": texto_llm(c.reason)}
                    if c else dict(CLASIFICACION_NEUTRA))
            cl = clasificaciones[msg["message_id"]]
            if es_oportunidad(cl):
                oportunidades.append({**msg, **cl, "opportunity_id": f"OPP-{len(oportunidades) + 1:03d}"})
    return {"clasificaciones": clasificaciones, "oportunidades": oportunidades}


def hay_oportunidades(state: AgentState) -> str:
    """Arista condicional: ¿hay oportunidades que pasen el umbral?"""
    return "generar_contenido" if state.get("oportunidades") else "solo_analitica"
