"""
CommunityLab AI - Orchestrator (Modo Batch Optimizado)
"""
from typing import List, Tuple, Optional
from src.domain.schemas import (
    RawMessageInteraction, 
    ProcessedMessage, 
    GeneratedAssets,
    SemanticAnalysis,
    OpportunityResult,
    OpportunityType,
    PostLinkedIn,
    DestaqueNewsletter
)
from src.utils.sanitizer import anonimizar_texto, anonimizar_autor
from src.core.agents.batch_agent import analyze_batch_with_llm
from src.core.agents.detector import detect_opportunity
from src.utils.logger import setup_logger

logger = setup_logger("orchestrator")


def process_batch_pipeline(interactions: List[RawMessageInteraction]) -> Tuple[List[Tuple[ProcessedMessage, Optional[GeneratedAssets]]], dict]:
    """
    Procesa un conjunto de mensajes en UNA SOLA llamada a la IA.
    Garantiza que TODOS los mensajes (aprobados y descartados) permanezcan en los resultados.
    """
    # 1. Sanitización preventiva
    sanitized_batch = []
    # Guardamos los mensajes en orden original usando una lista y un diccionario
    mensajes_ordenados = []
    for m in interactions:
        c_text = anonimizar_texto(m.texto)
        c_auth = anonimizar_autor(m.autor)
        item = {
            "message_id": m.message_id,
            "autor": c_auth,
            "channel": m.channel,
            "texto": c_text,
            "reacciones": m.metadata.get("reacciones", 0)
        }
        sanitized_batch.append(item)
        mensajes_ordenados.append((m, c_auth, c_text))

    # 2. Invocación única a Gemini
    batch_result = analyze_batch_with_llm(sanitized_batch)

    final_results = []
    resumen = {
        "total_procesados": len(interactions),
        "sentimiento_predominante": "Positivo",
        "temas_principales": ["Comunidad Tech"]
    }

    if batch_result:
        resumen["sentimiento_predominante"] = batch_result.resumen_lote.get("sentimiento_predominante", "Positivo")
        resumen["temas_principales"] = batch_result.resumen_lote.get("temas_en_tendencia", ["Comunidad"])

        # Mapear las oportunidades que la IA seleccionó (las >= 0.70)
        op_map = {op.message_id: op for op in batch_result.oportunidades}

        # RECORREMOS CADA UNO DE LOS MENSAJES ORIGINALES (Para no perder ninguno)
        for raw, c_auth, c_text in mensajes_ordenados:
            m_id = raw.message_id

            if m_id in op_map:
                # Caso A: Fue seleccionado por la IA (Score >= 0.70)
                op_data = op_map[m_id]
                analysis = SemanticAnalysis(
                    sentiment="positive" if op_data.tipo_oportunidad == OpportunityType.SUCCESS_STORY else "neutral",
                    topics=resumen["temas_principales"],
                    relevance_score=op_data.opportunity_score,
                    intent=op_data.tipo_oportunidad.value
                )
                op_res = OpportunityResult(
                    type=op_data.tipo_oportunidad,
                    opportunity_score=op_data.opportunity_score,
                    reason=op_data.razon
                )

                title = op_data.post_linkedin_titulo or (op_data.post_linkedin.get("titulo") if op_data.post_linkedin else None) or "Hito de la Comunidad"
                copy = op_data.post_linkedin_copy or (op_data.post_linkedin.get("copy") if op_data.post_linkedin else None) or c_text

                news_dict = op_data.newsletter or (op_data.post_linkedin.get("newsletter") if isinstance(op_data.post_linkedin, dict) else None)
                news_title = op_data.newsletter_titular or (news_dict.get("titular") if isinstance(news_dict, dict) else "Novedad Tech")
                news_summary = op_data.newsletter_resumen or (news_dict.get("resumen") if isinstance(news_dict, dict) else c_text[:120])

                assets = GeneratedAssets(
                    post_linkedin=PostLinkedIn(
                        titulo=title,
                        texto_copy=copy,
                        canal_recomendado="LinkedIn Oficial",
                        potencial_engagement="Alto"
                    ),
                    destaque_newsletter_semanal=DestaqueNewsletter(
                        seccion="Comunidad",
                        titular=news_title,
                        resumen=news_summary
                    )
                )
                proc = ProcessedMessage(
                    message_id=raw.message_id, channel=raw.channel, autor_anonimizado=c_auth,
                    texto_limpio=c_text, analysis=analysis, opportunity=op_res
                )
                final_results.append((proc, assets))

            else:
                # Caso B: Fue descartado por la IA (< 0.70) -> ¡AQUÍ ESTABAN LOS 21 FALTANTES!
                analysis = SemanticAnalysis(
                    sentiment="neutral", 
                    topics=["Conversación casual"], 
                    relevance_score=0.30,
                    intent="descartado"
                )
                op_res = OpportunityResult(
                    type=OpportunityType.NONE, 
                    opportunity_score=0.30, 
                    reason="Descartado por la IA: conversación informal sin valor para marketing."
                )
                proc = ProcessedMessage(
                    message_id=raw.message_id, channel=raw.channel, autor_anonimizado=c_auth,
                    texto_limpio=c_text, analysis=analysis, opportunity=op_res
                )
                final_results.append((proc, None))

        return final_results, resumen

    # 3. Fallback Heurístico si la API falla
    logger.warning("Usando pipeline heurístico de contingencia.")
    for raw, c_auth, c_text in mensajes_ordenados:
        analysis = SemanticAnalysis(sentiment="neutral", topics=["Comunidad"], relevance_score=0.5)
        op_res = detect_opportunity(c_text, raw.tipo_declarado, analysis, raw.metadata)
        assets = None
        if op_res.opportunity_score >= 0.70:
            assets = GeneratedAssets(
                post_linkedin=PostLinkedIn(
                    titulo="De la Formación al Mercado Tech 🚀",
                    texto_copy=f"¡Orgullo en la comunidad! {c_auth} nos comparte:\n\"{c_text}\"\n\n#TalentosTech #OracleCloud #ComunidadONE",
                    canal_recomendado="LinkedIn Oficial",
                    potencial_engagement="Alto"
                )
            )
        proc = ProcessedMessage(
            message_id=raw.message_id, channel=raw.channel, autor_anonimizado=c_auth,
            texto_limpio=c_text, analysis=analysis, opportunity=op_res
        )
        final_results.append((proc, assets))

    return final_results, resumen