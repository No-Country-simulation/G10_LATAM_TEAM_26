"""
Agente 1+2 compacto: Community Classifier
Una llamada por lote en lugar de dos: sentimiento, temas y tipo para todos los mensajes, y score con razón
solo para los candidatos a contenido. El umbral por tipo lo sigue aplicando el código (detector.es_oportunidad).
"""
from langchain_core.runnables import RunnableConfig

from src import config as ajustes
from src.adapters import cache_clasificacion
from src.adapters.llm.proveedores import invocar_lotes
from src.core.agents import simulado
from src.core.agents.detector import CLASIFICACION_NEUTRA, es_oportunidad
from src.core.agents.esquemas_llm import ClasificacionCompacta
from src.core.estado import AgentState
from src.core.prompts import PROMPT_CLASIFICADOR
from src.utils.logger import setup_logger
from src.utils.texto import json_mensajes, lotes, texto_llm

logger = setup_logger("community_classifier")

TIPOS_CON_CONTENIDO = set(ajustes.UMBRALES_POR_TIPO)


def _sin_candidatura(tipo: str) -> dict:
    """Clasificación de un mensaje que el modelo no propuso como candidato (queda bajo cualquier umbral)."""
    if tipo in TIPOS_CON_CONTENIDO:
        return {"type": tipo, "score": 0.3, "reason": "el modelo no lo propuso como candidato a contenido"}
    if tipo == "FEEDBACK":
        return {"type": tipo, "score": 0.1, "reason": "feedback para el equipo del programa; no genera contenido público"}
    return {"type": tipo, "score": 0.1, "reason": "sin valor para contenido público según su tipo"}


CAMPOS = ["message_id", "texto", "canal", "reacciones", "respuestas"]


def _resultado_llm(b, c) -> tuple:
    """Análisis y clasificación de un mensaje a partir de su resultado breve (b) y su candidatura (c)."""
    analisis = {
        "sentiment": b.sentiment if b else "neutral",
        "topics": [texto_llm(t).lower() for t in b.topics] if b else [],
        "intencion": "",
        "analisis_ok": b is not None,
    }
    if not b:
        clasificacion = dict(CLASIFICACION_NEUTRA)
    elif c and b.type in TIPOS_CON_CONTENIDO:
        clasificacion = {"type": b.type, "score": round(c.score, 2), "reason": texto_llm(c.reason)}
    else:
        clasificacion = _sin_candidatura(b.type)
    return analisis, clasificacion


def _interpretar(lote: list, respuesta) -> dict:
    """message_id -> (análisis, clasificación) para los mensajes de un lote a partir de la respuesta de la IA."""
    breves = {m.message_id: m for m in (respuesta.mensajes if respuesta else [])}
    candidatos = {c.message_id: c for c in (respuesta.candidatos if respuesta else [])}
    return {m["message_id"]: _resultado_llm(breves.get(m["message_id"]), candidatos.get(m["message_id"]))
            for m in lote}


def _avisar(al_avanzar, mensajes: list, resultados: dict) -> None:
    """Informa a quien observa (el panel) los mensajes recién clasificados; un fallo ahí no frena la clasificación."""
    if not al_avanzar:
        return
    try:
        al_avanzar([(m, *resultados[m["message_id"]]) for m in mensajes])
    except Exception as error:
        logger.warning(f"No se pudo informar el avance ({type(error).__name__})")


def _clasificar_con_ia(mensajes: list, al_avanzar=None) -> dict:
    """message_id -> (análisis, clasificación). Los mensajes ya clasificados salen de la caché; el resto va a la IA
    en lotes paralelos, y lo que la IA devuelve bien se guarda para la próxima vez.
    `al_avanzar(filas)` se llama con cada tanda lista: primero la caché, luego cada lote apenas responde."""
    claves = {m["message_id"]: cache_clasificacion.clave(PROMPT_CLASIFICADOR, m, CAMPOS) for m in mensajes}
    guardadas = cache_clasificacion.obtener(list(claves.values()))
    resultados = {mid: (e["analisis"], e["clasificacion"]) for mid, k in claves.items()
                  if (e := guardadas.get(k))}
    faltan = [m for m in mensajes if m["message_id"] not in resultados]
    if resultados:
        logger.info(f"Caché: {len(resultados)} de {len(mensajes)} mensajes ya clasificados")
        _avisar(al_avanzar, [m for m in mensajes if m["message_id"] in resultados], resultados)
    bloques = list(lotes(faltan))
    por_lote = {}

    def al_completar(indice, respuesta):
        por_lote[indice] = _interpretar(bloques[indice], respuesta)
        _avisar(al_avanzar, bloques[indice], por_lote[indice])

    if bloques:
        invocar_lotes(PROMPT_CLASIFICADOR, ClasificacionCompacta, "analisis", 0,
                      [{"mensajes": json_mensajes(lote, CAMPOS)} for lote in bloques], al_completar=al_completar)
    nuevas = {}
    for parciales in por_lote.values():
        for mid, (analisis, clasificacion) in parciales.items():
            resultados[mid] = (analisis, clasificacion)
            if analisis["analisis_ok"]:  # los omitidos por la IA no se guardan: se reintentan la próxima vez
                nuevas[claves[mid]] = {"analisis": analisis, "clasificacion": clasificacion}
    cache_clasificacion.guardar(nuevas)
    return resultados


def community_classifier(state: AgentState, config: RunnableConfig = None):
    """Nodo de clasificación compacta del grafo. Si la llamada trae configurable.al_avanzar, lo usa para ir
    informando los mensajes clasificados lote por lote."""
    al_avanzar = ((config or {}).get("configurable") or {}).get("al_avanzar")
    mensajes = state["interacciones_originales"]
    if state.get("simulado"):
        resultados = {m["message_id"]: (simulado.analisis(m), simulado.clasificacion(m)) for m in mensajes}
        _avisar(al_avanzar, mensajes, resultados)
    else:
        resultados = _clasificar_con_ia(mensajes, al_avanzar)
    analizados, clasificaciones, oportunidades = [], {}, []
    for msg in mensajes:  # en el orden del lote, para que los opportunity_id no dependan de la caché
        mid = msg["message_id"]
        analisis, clasificacion = resultados[mid]
        analizados.append({**msg, **analisis})
        clasificaciones[mid] = dict(clasificacion)
        if es_oportunidad(clasificaciones[mid]):
            oportunidades.append({**analizados[-1], **clasificaciones[mid],
                                  "opportunity_id": f"OPP-{len(oportunidades) + 1:03d}"})
    return {"mensajes_analizados": analizados, "clasificaciones": clasificaciones, "oportunidades": oportunidades}
