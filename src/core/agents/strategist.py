"""
Agente 3: Content Strategist
Redacta un borrador por cada formato que corresponde al tipo de oportunidad, en lotes por formato.
"""
import json
from collections import Counter
from typing import Any, Dict, List, Optional

from src import config
from src.adapters.llm.proveedores import invocar, invocar_lotes
from src.core.agents import simulado
from src.core.agents.esquemas_llm import Borrador, BorradorLote
from src.core.estado import AgentState
from src.core.prompts import PROMPTS_REDACCION, PROMPTS_REGENERACION
from src.utils.logger import setup_logger
from src.utils.texto import hashtags, lotes, texto_llm

logger = setup_logger("content_strategist")

FORMATOS_POR_TIPO = {
    "SUCCESS_STORY": ["post_linkedin", "destaque_newsletter"],
    "LOGRO": ["post_linkedin"],
    "FAQ": ["sugerencia_faq"],
}
CANALES = {"post_linkedin": "LinkedIn Oficial"}
PREFIJOS = {"post_linkedin": "POST", "destaque_newsletter": "NEWS", "sugerencia_faq": "FAQ"}


def _origen(opp: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "message_id": opp["message_id"],
        "opportunity_id": opp["opportunity_id"],
        "channel": opp.get("canal"),
        "autor": opp.get("autor"),
        "message": opp["texto"],
        "sentiment": opp["sentiment"],
        "topics": opp["topics"],
        "type": opp["type"],
        "score": opp["score"],
        "reason": opp["reason"],
    }


def _contenido(formato: str, b: Borrador) -> Dict[str, Any]:
    if formato == "post_linkedin":
        return {
            "titulo": texto_llm(b.titulo),
            "copy": texto_llm(b.cuerpo),
            "hashtags": hashtags(b.hashtags),
            "canal_recomendado": CANALES[formato],
            "potencial_engagement": b.potencial_engagement or "medio",
        }
    if formato == "destaque_newsletter":
        return {"seccion": texto_llm(b.seccion) or "Logro de la Semana",
                "titular": texto_llm(b.titulo), "resumen": texto_llm(b.cuerpo)}
    return {"tema": texto_llm(b.titulo), "cuerpo": texto_llm(b.cuerpo),
            "origen_descripcion": texto_llm(b.origen_descripcion)}


def _entrada_pieza(pieza: Dict[str, Any]) -> Dict[str, Any]:
    opp = pieza["opp"]
    return {"pieza_id": pieza["pieza_id"], "tipo": opp["type"], "canal": opp.get("canal"),
            "mensaje": opp["texto"], "temas": opp["topics"]}


def planificar_piezas(oportunidades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Una pieza por cada formato que corresponde al tipo de oportunidad, con su activo_id fijado de antemano
    (así el id no depende del orden en que la IA termine cada lote)."""
    piezas, contadores = [], Counter()
    for opp in oportunidades:
        for formato in FORMATOS_POR_TIPO.get(opp["type"], []):
            contadores[formato] += 1
            piezas.append({"pieza_id": f"{opp['opportunity_id']}:{formato}", "formato": formato, "opp": opp,
                           "activo_id": f"{PREFIJOS[formato]}-{contadores[formato]:03d}", "orden": len(piezas)})
    return piezas


def lotes_de_piezas(piezas: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Lotes de un solo formato: cada llamada lleva solo el prompt de ese formato."""
    return [lote for formato in PROMPTS_REDACCION
            for lote in lotes([p for p in piezas if p["formato"] == formato], config.TAMANO_LOTE_CONTENIDO)]


def _entrada_lote(lote: List[Dict[str, Any]]) -> Dict[str, str]:
    return {"piezas": json.dumps([_entrada_pieza(p) for p in lote], ensure_ascii=False)}


def redactar_lote(lote: List[Dict[str, Any]], modo_simulado: bool = False) -> Dict[str, Borrador]:
    """Redacta un lote y devuelve los borradores por pieza_id (vacío si el lote falla)."""
    if modo_simulado:
        return {p["pieza_id"]: simulado.borrador(p["pieza_id"], p["opp"]["texto"]) for p in lote}
    try:
        r = invocar(PROMPTS_REDACCION[lote[0]["formato"]], BorradorLote, "redaccion", 0.4, _entrada_lote(lote))
    except Exception as error:
        logger.error(f"Un lote de redacción falló ({type(error).__name__}); se marca como pendiente")
        return {}
    return {b.pieza_id: b for b in (r.borradores if r else [])}


def construir_activo(pieza: Dict[str, Any], borrador: Borrador) -> Dict[str, Any]:
    return {
        "activo_id": pieza["activo_id"],
        "formato": pieza["formato"],
        "estado_curaduria": "borrador",
        "origen": _origen(pieza["opp"]),
        "contenido": _contenido(pieza["formato"], borrador),
    }


def content_strategist(state: AgentState):
    """Nodo 3 del grafo: redacta todas las piezas, con los lotes en paralelo."""
    piezas = planificar_piezas(state["oportunidades"])
    bloques = lotes_de_piezas(piezas)
    if state.get("simulado"):
        por_id = {pid: b for lote in bloques for pid, b in redactar_lote(lote, modo_simulado=True).items()}
    else:
        resultados = invocar_lotes([PROMPTS_REDACCION[lote[0]["formato"]] for lote in bloques], BorradorLote,
                                   "redaccion", 0.4, [_entrada_lote(lote) for lote in bloques])
        por_id = {b.pieza_id: b for r in resultados if r for b in r.borradores}
    activos = [construir_activo(p, por_id[p["pieza_id"]]) for p in piezas if p["pieza_id"] in por_id]
    pendientes = [p["pieza_id"] for p in piezas if p["pieza_id"] not in por_id]
    if pendientes:
        logger.warning(f"El modelo no devolvió {len(pendientes)} pieza(s): {pendientes}")
    return {"activos_generados": activos, "piezas_pendientes": pendientes}


def regenerar_pieza(activo: Dict[str, Any], indicaciones: str, modo_simulado: bool = False) -> Optional[Dict[str, Any]]:
    """Reescribe un activo aplicando las indicaciones del curador. Devuelve el contenido nuevo o None."""
    formato = activo["formato"]
    pieza_id = activo["activo_id"]
    if modo_simulado:
        nuevo = simulado.borrador(pieza_id, activo["origen"]["message"])
        nuevo.cuerpo = f"[SIMULADO — regenerado con: {indicaciones}]"
        return _contenido(formato, nuevo)
    try:
        r = invocar(PROMPTS_REGENERACION[formato], BorradorLote, "redaccion", 0.4, {
            "mensaje": activo["origen"]["message"],
            "borrador": json.dumps(activo["contenido"], ensure_ascii=False),
            "indicaciones": indicaciones or "mejora la redacción manteniendo las reglas",
            "pieza_id": pieza_id,
        })
    except Exception as error:
        logger.error(f"No se pudo regenerar {pieza_id}: {type(error).__name__}")
        return None
    return _contenido(formato, r.borradores[0]) if r and r.borradores else None
