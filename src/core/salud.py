"""
CommunityLab AI - Salud de la comunidad
Lectura del sentimiento del lote para el equipo y detección de mensajes que necesitan apoyo, a partir del paquete
(sin llamadas a la IA). El paquete guarda positive/neutral/negative (spec); la etiqueta es solo de presentación.
"""
from typing import Any, Dict, Tuple


def estado_general(distribucion: Dict[str, int]) -> Tuple[str, str]:
    """Traduce la distribución del lote a una lectura para el equipo: (emoji, etiqueta)."""
    total = sum(distribucion.values())
    if not total:
        return "—", "Sin datos"
    pos, neg, neu = (distribucion.get(s, 0) / total for s in ("positive", "negative", "neutral"))
    if neg >= 0.3:
        return "😟", "Con dificultades"
    if pos > 0.7:
        return "🤩", "Altamente positivo"
    if pos >= 0.4 and pos > neg:
        return "😊", "Mayormente positivo"
    if neu >= 0.6:
        return "😐", "Mayormente neutral"
    return "🤔", "Mixto"


def necesita_apoyo(p: Dict[str, Any]) -> bool:
    """Mensaje con sentimiento negativo o feedback sobre el programa."""
    return p["analysis"]["sentiment"] == "negative" or p["opportunity"]["type"] == "FEEDBACK"
