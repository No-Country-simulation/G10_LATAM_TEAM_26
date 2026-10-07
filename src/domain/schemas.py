"""
CommunityLab AI - Domain Schemas (Pydantic Contracts)
Contratos universales y trazables para el pipeline, la UI y la persistencia en OCI.
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
    """Estructura de entrada de cada interacción cruda o normalizada."""
    message_id: str
    source: str = "discord"
    channel: str
    timestamp: str = ""
    autor: str
    tipo_declarado: Optional[str] = "conversacion"
    texto: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchInputPayload(BaseModel):
    """Lote de entrada completo (Formato A)."""
    formato_version: str = "1.0"
    origen_comunidad: str = "Discord_Comunidad"
    periodo_referencia: str = "Semana_04"
    fecha_ingesta: Optional[str] = None
    interacciones: List[RawMessageInteraction] = Field(default_factory=list)


class SemanticAnalysis(BaseModel):
    """Salida del análisis semántico."""
    sentiment: str = "neutral"
    topics: List[str] = Field(default_factory=list)
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    intent: Optional[str] = None


class OpportunityResult(BaseModel):
    """Resultado del scoring de oportunidad."""
    type: OpportunityType = OpportunityType.NONE
    opportunity_score: float = Field(default=0.3, ge=0.0, le=1.0)
    reason: str = "Evaluado"


class ProcessedMessage(BaseModel):
    """Mensaje enriquecido y sanitizado."""
    message_id: str
    channel: str
    autor_anonimizado: str
    texto_limpio: str
    analysis: SemanticAnalysis
    opportunity: OpportunityResult


# ─── ACTIVOS DE MARKETING MULTIFORMATO ───────────────────────────────────────

class PostLinkedIn(BaseModel):
    titulo: str
    texto_copy: str = Field(..., alias="copy", serialization_alias="copy")
    canal_recomendado: str = "LinkedIn Oficial"
    potencial_engagement: str = "Alto"

    model_config = {
        "populate_by_name": True
    }


class DestaqueNewsletter(BaseModel):
    seccion: str = "Comunidad"
    titular: str
    resumen: str


class SugerenciaFAQ(BaseModel):
    tema: str
    origen: str = ""
    status: str = "derivado_a_mentoria"


class GeneratedAssets(BaseModel):
    post_linkedin: Optional[PostLinkedIn] = None
    destaque_newsletter_semanal: Optional[DestaqueNewsletter] = None
    sugerencia_contenido_faq: Optional[SugerenciaFAQ] = None

class ResumenComunidad(BaseModel):
    total_interacciones_procesadas: int = 0
    sentimiento_predominante: str = "Positivo"
    temas_principales: List[str] = Field(default_factory=list)


class AlmacenamientoOCI(BaseModel):
    bucket: str = "communitylab-bucket"
    ruta_objeto: str = ""
    status: str = "guardado_con_exito"


class PaqueteDistribucion(BaseModel):
    """Esquema oficial Formato B exigido en la pág 5 del PDF de la Hackathon."""
    status: str = "exito"
    resumen_comunidad: Dict[str, Any] = Field(default_factory=dict)
    activos_distribucion_generados: GeneratedAssets = Field(default_factory=GeneratedAssets)
    almacenamiento_oci: Optional[Dict[str, str]] = None


# Alias para compatibilidad con código anterior
FinalBatchOutput = PaqueteDistribucion