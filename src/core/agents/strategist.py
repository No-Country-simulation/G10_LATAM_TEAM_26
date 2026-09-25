"""
Agente 3: Content Strategist (Blindado contra fallos de parsing)
"""
import os
import re
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from src.domain.schemas import GeneratedAssets, PostLinkedIn, DestaqueNewsletter, OpportunityType
from src.utils.logger import setup_logger

load_dotenv()
logger = setup_logger("content_strategist")

COPYWRITER_SYSTEM_PROMPT = """Eres un Copywriter profesional para LinkedIn.
Tu objetivo es redactar publicaciones inspiradoras y humanas sobre logros y preguntas técnicas de la comunidad.
Mantén los textos directos, sin repeticiones de palabras y con 4 hashtags relevantes (#TalentosTech #OracleCloud #LangChain).
"""


def generate_content_assets(
    clean_text: str, 
    author: str, 
    op_type: OpportunityType, 
    reason: str,
    feedback_usuario: str = ""
) -> GeneratedAssets:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

    if api_key and api_key != "tu_api_key_aqui":
        try:
            llm = ChatGoogleGenerativeAI(
                model=model_name,
                api_key=api_key,
                max_output_tokens=800
            )
            structured_llm = llm.with_structured_output(GeneratedAssets)
            instruccion = f"\nInstrucción editorial: {feedback_usuario}" if feedback_usuario else ""
            prompt = f"Autor: {author}\nTipo: {op_type.value}\nMensaje original:\n\"{clean_text}\"{instruccion}"

            resultado = structured_llm.invoke([("system", COPYWRITER_SYSTEM_PROMPT), ("human", prompt)])
            if resultado and resultado.post_linkedin:
                return resultado
        except Exception as e:
            logger.warning(f"Error generando assets con {model_name}: {str(e)[:120]}. Usando fallback.")

    # Fallback seguro contextual
    hook = "¡De la comunidad al mercado laboral tech! 🚀"
    if "cv" in clean_text.lower():
        hook = "De no saber cómo armar el CV a su primer empleo como Dev 💼"
    elif "contrat" in clean_text.lower() or "primer trabajo" in clean_text.lower():
        hook = "Historias de éxito: Talento que transforma su carrera con IA y Cloud 🌟"

    if feedback_usuario:
        hook += f" • {feedback_usuario[:25]}"

    return GeneratedAssets(
        post_linkedin=PostLinkedIn(
            titulo=hook,
            texto_copy=f"¡Orgullo absoluto en nuestra comunidad! 👏\n\n{author} compartió un logro inspirador:\n\"{clean_text}\"\n\nCuando combinas disciplina, proyectos reales y una comunidad activa, los resultados llegan.\n\n¡Felicitaciones {author}! A seguir creciendo. 💫\n\n#TalentosTech #OracleCloud #LangChain #CarreraDev #ComunidadONE",
            canal_recomendado="LinkedIn Oficial",
            potencial_engagement="Alto"
        ),
        destaque_newsletter_semanal=DestaqueNewsletter(
            seccion="Historias de Éxito",
            titular=f"{author} conquista su meta laboral en tech",
            resumen=clean_text[:140] + "..."
        )
    )