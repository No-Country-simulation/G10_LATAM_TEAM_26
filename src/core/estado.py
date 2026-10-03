"""
CommunityLab AI - Estado compartido del grafo
"""
from typing import Any, Dict, List, TypedDict


class AgentState(TypedDict, total=False):
    simulado: bool                                  # modo sin IA (lo fija procesar())
    interacciones_originales: List[Dict[str, Any]]
    metadatos_lote: Dict[str, Any]
    mensajes_analizados: List[Dict[str, Any]]
    clasificaciones: Dict[str, Dict[str, Any]]
    oportunidades: List[Dict[str, Any]]
    activos_generados: List[Dict[str, Any]]
    piezas_pendientes: List[str]                    # piezas que la IA no devolvió
    paquete_final: Dict[str, Any]
