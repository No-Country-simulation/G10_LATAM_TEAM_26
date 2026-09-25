"""
CommunityLab AI - Unit Tests
Valida la anonimización de PII, esquemas de datos y scoring algorítmico.
"""
import pytest
from src.utils.sanitizer import anonimizar_texto, anonimizar_autor
from src.domain.schemas import OpportunityResult, OpportunityType, SemanticAnalysis
from src.core.agents.detector import detect_opportunity


def test_anonimizar_autor():
    assert anonimizar_autor("Mariana Souza") == "Mariana S."
    assert anonimizar_autor("Lucas Albuquerque") == "Lucas A."
    assert anonimizar_autor("Pedro") == "Pedro"
    assert anonimizar_autor("") == "Miembro Anónimo"


def test_anonimizar_texto_pii():
    texto_con_email = "Hola, escríbeme a valeria@correo.com para pasarte el link."
    limpio = anonimizar_texto(texto_con_email)
    assert "valeria@correo.com" not in limpio
    assert "[EMAIL_PROTEGIDO]" in limpio

    texto_con_mencion = "Muchas gracias a <@!123456789> por la ayuda."
    assert "@miembro" in anonimizar_texto(texto_con_mencion)


def test_scoring_success_story():
    texto = "¡Conseguí trabajo como Data Analyst Jr gracias al bootcamp!"
    analysis = SemanticAnalysis(
        sentiment="positive",
        topics=["Empleo", "Data"],
        relevance_score=0.95
    )
    resultado = detect_opportunity(texto, "testimonio", analysis, {"reacciones": 10, "respuestas": 5})
    
    assert resultado.type == OpportunityType.SUCCESS_STORY
    assert resultado.opportunity_score >= 0.70


def test_scoring_saludo_descartado():
    texto = "Holaaa a todos, buen día"
    analysis = SemanticAnalysis(
        sentiment="neutral",
        topics=["General"],
        relevance_score=0.30
    )
    resultado = detect_opportunity(texto, "conversacion", analysis, {"reacciones": 0, "respuestas": 0})
    
    assert resultado.type == OpportunityType.NONE
    assert resultado.opportunity_score < 0.70