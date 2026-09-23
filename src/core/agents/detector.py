"""
Agente 2: Opportunity Detector
Calcula con precisión el Community Opportunity Score (0.00 a 1.00).
Alineado con la especificación técnica de CommunityLab AI.
"""
from src.domain.schemas import OpportunityResult, OpportunityType, SemanticAnalysis


def detect_opportunity(text: str, declared_type: str, analysis: SemanticAnalysis, metadata: dict) -> OpportunityResult:
    reacciones = metadata.get("reacciones", 0)
    respuestas = metadata.get("respuestas", 0)
    text_lower = text.lower()

    # 1. Detección de Casos de Éxito / Contrataciones / Logros
    palabras_exito = [
        "primer trabajo", "quede seleccionad", "quedé seleccionad", 
        "consegui trabajo", "conseguí trabajo", "nuevo trabajo",
        "contratad", "contrato", "ascenso", "oferta laboral",
        "ganamos", "certificaci", "100 estrellas"
    ]
    es_exito = declared_type in ["testimonio", "logro"] or any(p in text_lower for p in palabras_exito)

    # 2. Detección de Dudas Técnicas / FAQ
    palabras_faq = [
        "como estructurar", "cómo estructurar", "ejemplo practico", "ejemplo práctico",
        "duda", "error", "403", "401", "exception", "como configuro", "cómo configuro"
    ]
    es_faq = declared_type == "pregunta_tecnica" or any(p in text_lower for p in palabras_faq)

    # 3. Cálculo del Opportunity Score según la matriz de la especificación
    if es_exito:
        op_type = OpportunityType.SUCCESS_STORY
        reason = "El usuario comparte un logro profesional o contratación laboral de alto impacto."
        base_score = 0.92  # Rango Alta Prioridad (0.90 - 1.00)

    elif es_faq and ("?" in text or "¿" in text or len(text) > 40):
        op_type = OpportunityType.FAQ
        reason = "Consulta técnica recurrente de la comunidad ideal para tutorial o tip rápido."
        base_score = 0.78  # Rango Media Prioridad (0.70 - 0.89)

    elif declared_type == "feedback":
        op_type = OpportunityType.FEEDBACK
        reason = "Retroalimentación sobre los cursos o mentorías."
        base_score = 0.72

    else:
        op_type = OpportunityType.NONE
        reason = "Mensaje casual o saludo sin relevancia para marketing."
        base_score = 0.30  # Rango Baja Prioridad (0.00 - 0.69)

    # Bonificación por engagement comunitario (reacciones en Discord)
    engagement_bonus = min(0.08, (reacciones * 0.005) + (respuestas * 0.01))
    final_score = round(min(1.0, base_score + engagement_bonus), 2)

    return OpportunityResult(
        type=op_type,
        opportunity_score=final_score,
        reason=reason
    )