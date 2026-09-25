"""
CommunityLab AI - Batch Intelligence Agent
Procesa múltiples interacciones en una sola llamada a Gemini con parseo defensivo.
"""
import os
import json
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import google.generativeai as genai
from pydantic import BaseModel, Field

from src.domain.schemas import OpportunityType
from src.utils.logger import setup_logger

load_dotenv()
logger = setup_logger("batch_agent")

BATCH_SYSTEM_PROMPT = """Eres el motor de curaduría de CommunityLab AI.
Evalúa el lote de mensajes y retorna ÚNICAMENTE un JSON con esta estructura exacta:

{
  "resumen_lote": {
    "total_evaluados": int,
    "sentimiento_predominante": "Altamente Positivo" | "Positivo" | "Neutral",
    "temas_en_tendencia": ["Tema1", "Tema2"]
  },
  "oportunidades": [
    {
      "message_id": "ID original del mensaje",
      "autor": "Nombre del autor",
      "channel": "canal",
      "tipo_oportunidad": "SUCCESS_STORY" | "FAQ" | "FEEDBACK" | "MILESTONE",
      "opportunity_score": float (0.70 a 1.00),
      "razon": "Explicación breve de la oportunidad",
      "post_linkedin_titulo": "Hook de impacto para LinkedIn",
      "post_linkedin_copy": "Copy persuasivo con felicitación y hashtags (#TalentosTech #OracleCloud)",
      "newsletter_titular": "Titular breve",
      "newsletter_resumen": "Resumen informativo de una línea"
    }
  ]
}

REGLAS:
1. Solo incluye mensajes con Score >= 0.70 (contrataciones, dudas técnicas relevantes, feedback).
2. Saludos o mensajes casuales NO deben incluirse en 'oportunidades'.
3. Retorna exclusivamente el JSON sin bloques de texto adicionales.
"""


class EvaluatedOpportunity(BaseModel):
    message_id: str
    autor: str
    channel: str
    tipo_oportunidad: OpportunityType
    opportunity_score: float = Field(default=0.80, ge=0.0, le=1.0)
    razon: str = "Oportunidad detectada por IA"
    
    # Campos planos para evitar errores de anidamiento de la IA
    post_linkedin_titulo: Optional[str] = None
    post_linkedin_copy: Optional[str] = None
    newsletter_titular: Optional[str] = None
    newsletter_resumen: Optional[str] = None

    # Compatibilidad por si la IA devuelve objetos anidados
    post_linkedin: Optional[Dict[str, Any]] = None
    newsletter: Optional[Dict[str, Any]] = None


class BatchProcessingResult(BaseModel):
    resumen_lote: Dict[str, Any] = Field(default_factory=dict)
    oportunidades: List[EvaluatedOpportunity] = Field(default_factory=list)


def _limpiar_json(raw_text: str) -> str:
    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if match:
        return match.group(0)
    return raw_text.strip()


def analyze_batch_with_llm(messages_payload: List[Dict[str, Any]]) -> Optional[BatchProcessingResult]:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()

    if not api_key or api_key == "tu_api_key_aqui":
        return None

    try:
        genai.configure(api_key=api_key)
        
        generation_config = {
            "response_mime_type": "application/json",
            "temperature": 0.2,
            "max_output_tokens": 4000
        }

        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=BATCH_SYSTEM_PROMPT,
            generation_config=generation_config
        )

        prompt = f"LOTE DE MENSAJES A EVALUAR:\n{json.dumps(messages_payload, ensure_ascii=False, indent=2)}"
        
        logger.info(f"Enviando lote de {len(messages_payload)} mensajes a Gemini ({model_name})...")
        response = model.generate_content(prompt)

        if not response or not response.text:
            return None

        clean_json = _limpiar_json(response.text)
        data = json.loads(clean_json)
        return BatchProcessingResult(**data)

    except Exception as e:
        logger.error(f"Fallo en análisis por lote con Gemini: {str(e)}")
        return None