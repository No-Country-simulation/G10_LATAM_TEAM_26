"""
CommunityLab AI - Unified Fast Agent
Con mitigación estricta de bucles degenerativos y parseo resiliente.
"""
import os
import json
import re
from dotenv import load_dotenv
from typing import Optional
import google.generativeai as genai
from pydantic import BaseModel, Field
from src.domain.schemas import OpportunityType
from src.utils.logger import setup_logger

load_dotenv()
logger = setup_logger("unified_agent")

SYSTEM_PROMPT = """Eres el motor de CommunityLab AI. Evalúa el mensaje y devuelve ÚNICAMENTE un JSON válido sin texto adicional:
{
  "sentiment": "positive" | "neutral" | "negative",
  "topics": ["lista", "de", "temas"],
  "relevance_score": 0.0 a 1.0,
  "opportunity_type": "SUCCESS_STORY" | "FAQ" | "FEEDBACK" | "MILESTONE" | "NONE",
  "opportunity_score": 0.0 a 1.0,
  "reason": "explicación breve",
  "linkedin_title": "título concreto (si score >= 0.70)",
  "linkedin_copy": "copy persuasivo breve con hashtags (si score >= 0.70)",
  "newsletter_title": "titular (si score >= 0.70)",
  "newsletter_summary": "resumen breve (si score >= 0.70)"
}
"""


class UnifiedAnalysisResult(BaseModel):
    sentiment: str = "neutral"
    topics: list[str] = Field(default_factory=lambda: ["General"])
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    opportunity_type: OpportunityType = OpportunityType.NONE
    opportunity_score: float = Field(default=0.3, ge=0.0, le=1.0)
    reason: str = "Evaluado automáticamente"
    linkedin_title: Optional[str] = "Hito de la Comunidad"
    linkedin_copy: Optional[str] = ""
    newsletter_title: Optional[str] = ""
    newsletter_summary: Optional[str] = ""


def _limpiar_json(raw_text: str) -> str:
    """Extrae el bloque JSON válido si el modelo agrega texto extra o bloques markdown."""
    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if match:
        return match.group(0)
    return raw_text.strip()


def process_with_gemini(clean_text: str, author: str, channel: str) -> Optional[UnifiedAnalysisResult]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

    if not api_key or api_key == "tu_api_key_aqui":
        return None

    try:
        genai.configure(api_key=api_key)

        # Configuración anti-bucle: límite de tokens y temperatura balanceada
        generation_config = {
            "response_mime_type": "application/json",
            "max_output_tokens": 800,
            "temperature": 0.3
        }

        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_PROMPT,
            generation_config=generation_config
        )

        prompt = f"Canal: #{channel}\nAutor: {author}\nMensaje:\n\"{clean_text}\""
        response = model.generate_content(prompt)

        if not response or not response.text:
            return None

        clean_json_str = _limpiar_json(response.text)
        data = json.loads(clean_json_str)

        # Si el modelo generó bucle en el título, limpiarlo
        if data.get("linkedin_title") and len(data["linkedin_title"]) > 120:
            data["linkedin_title"] = data["linkedin_title"][:90] + "..."

        return UnifiedAnalysisResult(**data)

    except Exception as e:
        logger.warning(f"Excepción controlada en LLM ({model_name}): {str(e)[:150]}. Usando fallback.")
        return None