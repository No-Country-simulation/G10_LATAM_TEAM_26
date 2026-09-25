"""
CommunityLab AI - Modo simulado
Heurísticas sin IA para desarrollo, tests y demos sin cuota. Todo lo que producen va marcado [SIMULADO].
"""
import re
from typing import Any, Dict

from src import config
from src.core.agents.esquemas_llm import Borrador

_EXITO = re.compile(r"contrat|seleccionad|firmé|conseguí .*(trabajo|empleo)|primer (trabajo|empleo|contrato)"
                    r"|ascenso|desde el \w+ soy|soy (analista|desarrollador|dev|qa|data)", re.I)
_LOGRO = re.compile(r"certificaci|aprobé|terminé el curso|estrellas en github|gané|finalista", re.I)
_FEEDBACK = re.compile(r"sugiero|sugerencia|sería bueno|deberían|me gustaría que|va muy rápido|faltan ejercicios"
                       r"|podrían mejorar", re.I)
_SOCIAL = re.compile(r"felicit|gracias|buenos días|buenas tardes|buenas noches|jaja|😂|🎉|éxitos", re.I)


def analisis(msg: Dict[str, Any]) -> Dict[str, Any]:
    t = msg["texto"]
    social = bool(_SOCIAL.search(t)) and not _EXITO.search(t)
    return {"sentiment": "positive" if (_EXITO.search(t) or _SOCIAL.search(t)) else "neutral",
            "topics": [config.TEMA_SOCIAL] if social else ["general"],
            "intencion": "[SIMULADO]", "analisis_ok": True}


def clasificacion(msg: Dict[str, Any]) -> Dict[str, Any]:
    t = msg["texto"]
    if _EXITO.search(t):
        return {"type": "SUCCESS_STORY", "score": 0.9, "reason": "[SIMULADO] patrón de contratación/logro laboral"}
    if _LOGRO.search(t):
        return {"type": "MILESTONE", "score": 0.85, "reason": "[SIMULADO] patrón de logro/certificación"}
    if "feedback" in (msg.get("canal") or "") or _FEEDBACK.search(t):
        return {"type": "FEEDBACK", "score": 0.1, "reason": "[SIMULADO] opinión o sugerencia sobre el programa"}
    if "?" in t and len(t) > 60 and not _SOCIAL.search(t):
        return {"type": "FAQ", "score": 0.7, "reason": "[SIMULADO] pregunta con contexto"}
    return {"type": "NONE", "score": 0.1, "reason": "[SIMULADO] charla social o sin contexto"}


def borrador(pieza_id: str, texto: str) -> Borrador:
    return Borrador(pieza_id=pieza_id,
                    titulo=f"[SIMULADO] {texto[:50]}...",
                    cuerpo="[SIMULADO — con IA real acá va el borrador redactado]",
                    hashtags=["#CommunityLab"], potencial_engagement="medio",
                    seccion="Logro de la Semana", origen_descripcion="[SIMULADO]")
