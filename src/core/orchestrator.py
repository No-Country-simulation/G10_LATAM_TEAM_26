"""
CommunityLab AI - Orquestador
Grafo LangGraph del motor y su API pública, que usan el panel, el bot y el CLI:
  procesar()         lista de mensajes -> paquete de distribución (Formato B)
  procesar_detalle() además devuelve el análisis por mensaje (Formato P) y lo que quedó pendiente
  clasificar()       solo análisis y detección: el paquete sale sin activos, en segundos
  generar_contenido() redacta los activos de ese paquete en segundo plano
"""
from typing import Any, Dict, List, Optional

from langgraph.graph import END, StateGraph

from src import config
from src.core.agents.analyst import community_analyst
from src.core.agents.classifier import community_classifier
from src.core.agents.detector import hay_oportunidades, opportunity_detector
from src.core.agents.strategist import content_strategist
from src.core.estado import AgentState
from src.core.generacion import GeneracionEnSegundoPlano
from src.core.packager import avisos, empaquetar, formato_p
from src.utils.sanitizer import anonimizar_texto


def _etapa_clasificacion(workflow: StateGraph, modo: str) -> str:
    """Agrega los nodos de clasificación y devuelve el nombre del último."""
    if modo == "compacta":
        workflow.add_node("community_classifier", community_classifier)
        workflow.set_entry_point("community_classifier")
        return "community_classifier"
    workflow.add_node("community_analyst", community_analyst)
    workflow.add_node("opportunity_detector", opportunity_detector)
    workflow.set_entry_point("community_analyst")
    workflow.add_edge("community_analyst", "opportunity_detector")
    return "opportunity_detector"


def construir_grafo(modo: str = config.MODO_CLASIFICACION):
    workflow = StateGraph(AgentState)
    ultimo = _etapa_clasificacion(workflow, modo)
    workflow.add_node("content_strategist", content_strategist)
    workflow.add_node("empaquetar", empaquetar)
    workflow.add_conditional_edges(
        ultimo,
        hay_oportunidades,
        {"generar_contenido": "content_strategist", "solo_analitica": "empaquetar"},
    )
    workflow.add_edge("content_strategist", "empaquetar")
    workflow.add_edge("empaquetar", END)
    return workflow.compile()


def construir_grafo_clasificacion(modo: str = config.MODO_CLASIFICACION):
    """Primera etapa del modo por fases: clasificación sin redacción."""
    workflow = StateGraph(AgentState)
    workflow.add_edge(_etapa_clasificacion(workflow, modo), END)
    return workflow.compile()


app = construir_grafo()
app_clasificacion = construir_grafo_clasificacion()


def _preparar(interacciones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Descarta mensajes vacíos y enmascara correos, teléfonos y menciones antes de que lleguen a la IA."""
    return [{**m, "texto": anonimizar_texto(m["texto"].strip())}
            for m in interacciones if (m.get("texto") or "").strip()]


def ejecutar(interacciones: List[Dict[str, Any]], metadatos: Optional[Dict[str, Any]] = None,
             simulado: bool = False) -> AgentState:
    """Corre el grafo completo y devuelve el estado final."""
    return app.invoke({"interacciones_originales": _preparar(interacciones),
                       "metadatos_lote": metadatos or {},
                       "simulado": simulado})


def procesar(interacciones: List[Dict[str, Any]], metadatos: Optional[Dict[str, Any]] = None,
             simulado: bool = False) -> Dict[str, Any]:
    """Lista de mensajes -> paquete (Formato B). Sirve para lote (N mensajes) y tiempo real (lista de 1).
    No escribe archivos: guardar es decisión de quien llama. Con simulado=True no llama a la IA."""
    return ejecutar(interacciones, metadatos, simulado)["paquete_final"]


def procesar_detalle(interacciones: List[Dict[str, Any]], metadatos: Optional[Dict[str, Any]] = None,
                     simulado: bool = False) -> Dict[str, Any]:
    """Como procesar(), pero también devuelve el análisis por mensaje (Formato P) y los avisos."""
    estado = ejecutar(interacciones, metadatos, simulado)
    return {"paquete": estado["paquete_final"], "procesados": formato_p(estado),
            "avisos": avisos(estado), "estado": estado}


def clasificar(interacciones: List[Dict[str, Any]], metadatos: Optional[Dict[str, Any]] = None,
               simulado: bool = False) -> Dict[str, Any]:
    """Como procesar_detalle(), pero sin redactar: el paquete sale con la lista de activos vacía."""
    estado = app_clasificacion.invoke({"interacciones_originales": _preparar(interacciones),
                                       "metadatos_lote": metadatos or {},
                                       "simulado": simulado})
    estado.update(activos_generados=[], piezas_pendientes=[])
    paquete = empaquetar(estado)["paquete_final"]
    return {"paquete": paquete, "procesados": formato_p(estado), "avisos": avisos(estado), "estado": estado}


def generar_contenido(detalle: Dict[str, Any], simulado: bool = False) -> GeneracionEnSegundoPlano:
    """Redacta en segundo plano los activos del paquete que devolvió clasificar()."""
    return GeneracionEnSegundoPlano(detalle["estado"], detalle["paquete"], simulado).iniciar()
