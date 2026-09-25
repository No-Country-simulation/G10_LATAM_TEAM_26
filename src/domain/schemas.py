"""
CommunityLab AI - Domain Schemas (Pydantic Contracts)
Define todos los modelos de datos para validación estricta y trazabilidad.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OpportunityType(str, Enum):
    SUCCESS_STORY = "SUCCESS_STORY"
    FAQ = "FAQ"
    TREND = "TREND"
    FEEDBACK = "FEEDBACK"
    MILESTONE = "MILESTONE"
    NONE = "NONE"


class SentimentType(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    HIGHLY_POSITIVE = "Altamente Positivo"


class RawMessageInteraction(BaseModel):
    """Estructura de cada interacción dentro del lote recibido."""
    message_id: str
    source: str = "discord"
    channel: str
    timestamp: str
    autor: str
    tipo_declarado: str
    texto: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchInputPayload(BaseModel):
    """Esquema de entrada para lotes de interacciones (ej: lote_ejemplo_formato_a.json)."""
    formato_version: str = "1.0"
    origen_comunidad: str
    periodo_referencia: str
    fecha_ingesta: Optional[str] = None
    interacciones: List[RawMessageInteraction]


class SemanticAnalysis(BaseModel):
    """Salida del Agente 1: Community Analyst."""
    sentiment: str
    topics: List[str]
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    intent: Optional[str] = None


class OpportunityResult(BaseModel):
    """Salida del Agente 2: Opportunity Detector."""
    type: OpportunityType
    opportunity_score: float = Field(..., ge=0.0, le=1.0)
    reason: str


class ProcessedMessage(BaseModel):
    """Mensaje enriquecido tras el paso de los agentes."""
    message_id: str
    channel: str
    autor_anonimizado: str
    texto_limpio: str
    analysis: SemanticAnalysis
    opportunity: OpportunityResult


# ─── ACTIVOS DE DISTRIBUCIÓN (Agente 3: Content Strategist) ─────────────────

class PostLinkedIn(BaseModel):
    titulo: str
    texto_copy: str = Field(..., alias="copy", serialization_alias="copy")
    canal_recomendado: str = "LinkedIn Oficial"
    potencial_engagement: str = "Alto"

    model_config = {
        "populate_by_name": True  # Permite acceder tanto por .texto_copy como por .copy
    }


class DestaqueNewsletter(BaseModel):
    seccion: str
    titular: str
    resumen: str


class SugerenciaFAQ(BaseModel):
    tema: str
    origen: str
    status: str = "derivado_a_mentoria"


class GeneratedAssets(BaseModel):
    post_linkedin: Optional[PostLinkedIn] = None
    destaque_newsletter_semanal: Optional[DestaqueNewsletter] = None
    sugerencia_contenido_faq: Optional[SugerenciaFAQ] = None


class FinalBatchOutput(BaseModel):
    """Formato de salida estructurada exigido por el PDF de la Hackathon."""
    status: str = "exito"
    resumen_comunidad: Dict[str, Any]
    activos_distribucion_generados: GeneratedAssets
    almacenamiento_oci: Optional[Dict[str, str]] = None