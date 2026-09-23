"""
CommunityLab AI - Orchestrator
Pipeline Multiagente de análisis, detección y curaduría de interacciones.
"""
from typing import Tuple, Optional
from src.domain.schemas import (
    RawMessageInteraction, 
    ProcessedMessage, 
    GeneratedAssets
)
from src.utils.sanitizer import anonimizar_texto, anonimizar_autor
from src.core.agents.analyst import analyze_message
from src.core.agents.detector import detect_opportunity
from src.core.agents.strategist import generate_content_assets
from src.utils.logger import setup_logger

logger = setup_logger("orchestrator")


def process_single_interaction(raw: RawMessageInteraction) -> Tuple[ProcessedMessage, Optional[GeneratedAssets]]:
    """
    Ejecuta el pipeline completo para una interacción:
    1. Sanitización de PII (texto y autor).
    2. Agente 1 (Community Analyst): Sentimiento, tópicos y relevancia.
    3. Agente 2 (Opportunity Detector): Scoring y clasificación.
    4. Bifurcación condicional (Agente 3 - Content Strategist): si Score >= 0.70 genera copys.
    """
    try:
        # Paso 1: Sanitización preventiva de PII
        clean_text = anonimizar_texto(raw.texto)
        clean_author = anonimizar_autor(raw.autor)

        # Paso 2: Análisis Semántico (Agente 1)
        analysis = analyze_message(clean_text, raw.tipo_declarado)

        # Paso 3: Detección y Priorización (Agente 2)
        opportunity = detect_opportunity(clean_text, raw.tipo_declarado, analysis, raw.metadata)

        # Ensamble del mensaje procesado trazable
        processed = ProcessedMessage(
            message_id=raw.message_id,
            channel=raw.channel,
            autor_anonimizado=clean_author,
            texto_limpio=clean_text,
            analysis=analysis,
            opportunity=opportunity
        )

        # Paso 4: Bifurcación condicional (Score >= 0.70)
        assets = None
        if opportunity.opportunity_score >= 0.70:
            assets = generate_content_assets(
                clean_text=clean_text,
                author=clean_author,
                op_type=opportunity.type,
                reason=opportunity.reason
            )

        return processed, assets

    except Exception as e:
        logger.error(f"Error procesando interacción {raw.message_id}: {str(e)}")
        raise e