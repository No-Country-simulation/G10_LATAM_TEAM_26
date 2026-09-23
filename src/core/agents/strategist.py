"""
Agente 3: Content Strategist
Genera activos de marketing estructurados (LinkedIn, FAQ, Newsletter).
"""
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from src.domain.schemas import GeneratedAssets, PostLinkedIn, DestaqueNewsletter, SugerenciaFAQ, OpportunityType
from src.utils.logger import setup_logger

logger = setup_logger("content_strategist")

COPYWRITER_PROMPT = """Eres un Content Strategist & Copywriter profesional especializado en marcas tecnológicas y formación de talento.
Tu objetivo es redactar publicaciones de alto impacto para LinkedIn y resúmenes para boletines a partir de logros o preguntas de la comunidad.
- Tono LinkedIn: Inspirador, humano, profesional, destacando el valor del aprendizaje práctico.
- Incluye gancho inicial, desarrollo breve, felicitación o llamado a la acción y 4-5 hashtags relevantes.
"""

def generate_content_assets(clean_text: str, author: str, op_type: OpportunityType, reason: str) -> GeneratedAssets:
    """Genera copys listos para publicación."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if api_key and api_key != "tu_api_key_aqui":
        try:
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0.7,
                api_key=api_key
            )
            structured_llm = llm.with_structured_output(GeneratedAssets)
            prompt = f"Autor: {author}\nTipo de Oportunidad: {op_type.value}\nRazón: {reason}\nMensaje original:\n\"{clean_text}\""
            return structured_llm.invoke([("system", COPYWRITER_PROMPT), ("human", prompt)])
        except Exception as e:
            logger.error(f"Error generando assets con Gemini: {str(e)}")

    # Plantilla profesional de fallback
    if op_type == OpportunityType.SUCCESS_STORY:
        return GeneratedAssets(
            post_linkedin=PostLinkedIn(
                titulo="De la Formación Práctica al Mercado: Historias que Inspiran 🚀",
                copy=f"¡Orgullo absoluto en nuestra comunidad! 👏\n\nNuestra estudiante {author} nos comparte un gran logro:\n\"{clean_text}\"\n\nDemostrar habilidades técnicas con proyectos reales marca la diferencia en cada proceso de selección.\n\n¡Felicitaciones {author}! A seguir conquistando metas. 💫\n\n#TalentosTech #OracleCloud #InteligenciaArtificial #ComunidadONE #CarreraDev",
                canal_recomendado="LinkedIn Oficial",
                potencial_engagement="Alto"
            ),
            destaque_newsletter_semanal=DestaqueNewsletter(
                seccion="Logros Destacados",
                titular=f"Estudiante {author} conquista hito profesional con proyectos de IA",
                resumen=clean_text[:120] + "..."
            )
        )
    elif op_type == OpportunityType.FAQ:
        return GeneratedAssets(
            sugerencia_contenido_faq=SugerenciaFAQ(
                tema=f"Guía Práctica sobre consulta de {author}",
                origen=clean_text[:80] + "...",
                status="derivado_a_mentoria"
            ),
            post_linkedin=PostLinkedIn(
                titulo="De la Formación Práctica al Mercado: Historias que Inspiran 🚀",
                texto_copy=f"¡Orgullo absoluto en nuestra comunidad! 👏\n\nNuestra estudiante {author} nos comparte un gran logro:\n\"{clean_text}\"\n\n¡Felicitaciones {author}! A seguir conquistando metas. 💫\n\n#TalentosTech #OracleCloud #InteligenciaArtificial #ComunidadONE",
                canal_recomendado="LinkedIn Oficial",
                potencial_engagement="Alto"
            )
        )
    return GeneratedAssets()