"""
CommunityLab AI - Agente Content Strategist
Genera activos de marketing multiformato con soporte de feedback humano interactivo.
"""
import os
import json
import re
from typing import Optional
from dotenv import load_dotenv
import google.generativeai as genai

from src.domain.schemas import GeneratedAssets, PostLinkedIn, DestaqueNewsletter, SugerenciaFAQ, OpportunityType
from src.utils.logger import setup_logger

load_dotenv()
logger = setup_logger("content_strategist")

COPYWRITER_SYSTEM_PROMPT = """Eres el Content Strategist de CommunityLab AI.
A partir de la historia del estudiante, genera un JSON válido:
{
  "post_linkedin": {
    "titulo": "Hook de impacto",
    "copy": "Copy persuasivo con hashtags (#TalentosTech #OracleCloud #LangChain)",
    "canal_recomendado": "LinkedIn Oficial",
    "potencial_engagement": "Alto"
  },
  "destaque_newsletter_semanal": {
    "seccion": "Comunidad",
    "titular": "Titular periodístico",
    "resumen": "Resumen de una o dos líneas"
  },
  "sugerencia_contenido_faq": {
    "tema": "Tema técnico",
    "origen": "Contexto",
    "status": "derivado_a_mentoria"
  },
  "prompt_imagen_flux": "A detailed 3D tech illustration in English reflecting the achievement (e.g. futuristic laptop with glowing code, graduation cap, modern isometric desk, trophy with cloud logo, vibrant tech lighting, clean background, 8k resolution)"
}
"""


def _limpiar_json(raw_text: str) -> str:
    # Eliminar bloques markdown de tipo ```json ... ``` si el modelo los añade
    texto_limpio = re.sub(r'```(?:json)?', '', raw_text).strip()
    match = re.search(r'\{.*\}', texto_limpio, re.DOTALL)
    if match:
        return match.group(0)
    return texto_limpio


def generate_content_assets(
    clean_text: str, 
    author: str, 
    op_type: OpportunityType, 
    reason: str,
    feedback_usuario: str = ""
) -> GeneratedAssets:
    """Genera activos multiformato con soporte para refinamiento editorial humano."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

    if api_key and api_key != "tu_api_key_aqui":
        try:
            genai.configure(api_key=api_key)
            generation_config = {
                "response_mime_type": "application/json",
                "temperature": 0.3,
                "max_output_tokens": 2000
            }
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=COPYWRITER_SYSTEM_PROMPT,
                generation_config=generation_config
            )

            instruccion = f"\nRetroalimentación adicional del editor: {feedback_usuario}" if feedback_usuario else ""
            prompt = f"Autor: {author}\nTipo: {op_type.value if hasattr(op_type, 'value') else op_type}\nRazón: {reason}\nMensaje original:\n\"{clean_text}\"{instruccion}"

            response = model.generate_content(prompt)
            if response and response.text:
                clean_json = _limpiar_json(response.text)
                data = json.loads(clean_json)

                p_data = data.get("post_linkedin", {})
                n_data = data.get("destaque_newsletter_semanal", {})
                f_data = data.get("sugerencia_contenido_faq", {})

                return GeneratedAssets(
                    post_linkedin=PostLinkedIn(
                        titulo=p_data.get("titulo", "Hito de la Comunidad"),
                        texto_copy=p_data.get("copy", clean_text),
                        canal_recomendado=p_data.get("canal_recomendado", "LinkedIn Oficial"),
                        potencial_engagement=p_data.get("potencial_engagement", "Alto")
                    ) if p_data else None,
                    destaque_newsletter_semanal=DestaqueNewsletter(
                        seccion=n_data.get("seccion", "Comunidad"),
                        titular=n_data.get("titular", "Logro Tech"),
                        resumen=n_data.get("resumen", clean_text[:140])
                    ) if n_data else None,
                    sugerencia_contenido_faq=SugerenciaFAQ(
                        tema=f_data.get("tema", "FAQ Técnica"),
                        origen=f_data.get("origen", clean_text[:80]),
                        status=f_data.get("status", "derivado_a_mentoria")
                    ) if f_data else None
                )
        except Exception as e:
            logger.warning(f"Error generando assets con Gemini ({model_name}): {str(e)[:120]}. Usando fallback.")

    # Fallback heurístico si no hay conexión o falla la llamada
    hook = "¡De la comunidad al mercado laboral tech! 🚀"
    if feedback_usuario:
        hook += f" • {feedback_usuario[:25]}"

    return GeneratedAssets(
        post_linkedin=PostLinkedIn(
            titulo=hook,
            texto_copy=f"¡Orgullo absoluto en nuestra comunidad! 👏\n\n{author} compartió un logro inspirador:\n\"{clean_text}\"\n\nCuando combinas disciplina, proyectos reales y una comunidad que respalda, las oportunidades llegan.\n\n¡Felicitaciones {author}! A seguir creciendo. 💫\n\n#TalentosTech #OracleCloud #LangChain #CarreraDev #ComunidadONE",
            canal_recomendado="LinkedIn Oficial",
            potencial_engagement="Alto"
        ),
        destaque_newsletter_semanal=DestaqueNewsletter(
            seccion="Historias de Éxito",
            titular=f"{author} conquista su meta laboral en tech",
            resumen=clean_text[:140] + "..."
        ),
        sugerencia_contenido_faq=SugerenciaFAQ(
            tema=f"Guía Práctica: Consulta destacada de {author}",
            origen=clean_text[:80],
            status="derivado_a_mentoria"
        )
    )