"""
CommunityLab AI - Unit Tests
Lectura de la salud de la comunidad a partir del sentimiento del lote (sin llamadas a la IA).
"""
from src.ui.components.salud import estado_general, necesita_apoyo


def test_estado_general_por_proporcion():
    assert estado_general({"positive": 8, "neutral": 2, "negative": 0})[1] == "Altamente positivo"
    assert estado_general({"positive": 5, "neutral": 4, "negative": 1})[1] == "Mayormente positivo"
    assert estado_general({"positive": 1, "neutral": 7, "negative": 1})[1] == "Mayormente neutral"
    assert estado_general({"positive": 4, "neutral": 3, "negative": 3})[1] == "Con dificultades"
    assert estado_general({"positive": 0, "neutral": 0, "negative": 0})[1] == "Sin datos"


def test_necesita_apoyo_por_sentimiento_o_feedback():
    def procesado(sentimiento, tipo):
        return {"analysis": {"sentiment": sentimiento}, "opportunity": {"type": tipo}}

    assert necesita_apoyo(procesado("negative", "FAQ"))
    assert necesita_apoyo(procesado("neutral", "FEEDBACK"))
    assert not necesita_apoyo(procesado("positive", "SUCCESS_STORY"))
