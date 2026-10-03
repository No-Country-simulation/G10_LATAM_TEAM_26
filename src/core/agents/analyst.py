"""
Agente 1: Community Analyst
Sentimiento, temas e intención de cada mensaje, en lotes.
"""
from src.adapters.llm.proveedores import invocar_lotes
from src.core.agents import simulado
from src.core.agents.esquemas_llm import AnalisisLote
from src.core.estado import AgentState
from src.core.prompts import PROMPT_ANALISTA
from src.utils.texto import json_mensajes, lotes, texto_llm


def community_analyst(state: AgentState):
    """Nodo 1 del grafo. El autor nunca se envía al modelo: solo id, texto y canal."""
    analizados = []
    bloques = list(lotes(state["interacciones_originales"]))
    resultados = [None] * len(bloques) if state.get("simulado") else invocar_lotes(
        PROMPT_ANALISTA, AnalisisLote, "analisis", 0,
        [{"mensajes": json_mensajes(lote, ["message_id", "texto", "canal"])} for lote in bloques])
    for lote, resultado in zip(bloques, resultados):
        por_id = {r.message_id: r for r in (resultado.mensajes if resultado else [])}
        for msg in lote:
            if state.get("simulado"):
                analizados.append({**msg, **simulado.analisis(msg)})
                continue
            r = por_id.get(msg["message_id"])
            analizados.append({
                **msg,
                "sentiment": r.sentiment if r else "neutral",
                "topics": [texto_llm(t).lower() for t in r.topics] if r else [],
                "intencion": texto_llm(r.intencion) if r else "",
                "analisis_ok": r is not None,
            })
    return {"mensajes_analizados": analizados}
