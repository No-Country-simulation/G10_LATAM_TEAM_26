"""
CommunityLab AI - Orchestrator
Pipeline Multiagente consolidado con Deduplicación OCI y Micro-Batching.
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
from src.adapters.db.repository import filter_unprocessed_interactions, save_processed_messages
from src.utils.logger import setup_logger

logger = setup_logger("orchestrator")


def process_batch_pipeline(interactions: List[RawMessageInteraction]) -> Tuple[List[Tuple[ProcessedMessage, Optional[GeneratedAssets]]], dict]:
    # 1. Filtro estricto contra Oracle Cloud (Deduplicación en OCI)
    mensajes_nuevos = filter_unprocessed_interactions(interactions)

    if not mensajes_nuevos:
        logger.info("Todos los mensajes ya existen en la base de datos de Oracle Cloud.")
        return [], {
            "total_procesados": 0, 
            "sentimiento_predominante": "N/A", 
            "temas_principales": ["Sin mensajes nuevos (Deduplicados en OCI)"]
        }

    # 2. Sanitización preventiva del lote
    sanitized_batch = []
    mensajes_ordenados = []
    for m in mensajes_nuevos:
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

    # 3. Invocación única al LLM
    batch_result = analyze_batch_with_llm(sanitized_batch)

    final_results = []
    resumen = {
        "total_procesados": len(mensajes_nuevos),
        "sentimiento_predominante": "Positivo",
        "temas_principales": ["Comunidad Tech"]
    }

    if batch_result:
        resumen["sentimiento_predominante"] = batch_result.resumen_lote.get("sentimiento_predominante", "Positivo")
        resumen["temas_principales"] = batch_result.resumen_lote.get("temas_en_tendencia", ["Comunidad"])
        op_map = {op.message_id: op for op in batch_result.oportunidades}

        for raw, c_auth, c_text in mensajes_ordenados:
            m_id = raw.message_id

            if m_id in op_map:
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
                analysis = SemanticAnalysis(sentiment="neutral", topics=["Conversación casual"], relevance_score=0.30, intent="descartado")
                op_res = OpportunityResult(type=OpportunityType.NONE, opportunity_score=0.30, reason="Conversación casual.")
                proc = ProcessedMessage(
                    message_id=raw.message_id, channel=raw.channel, autor_anonimizado=c_auth,
                    texto_limpio=c_text, analysis=analysis, opportunity=op_res
                )
                final_results.append((proc, None))

    # 4. Guardar en Oracle Cloud los mensajes procesados
    if final_results:
        save_processed_messages(final_results)

    return final_results, resumen