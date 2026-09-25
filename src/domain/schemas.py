"""
CommunityLab AI - Domain Schemas (Pydantic Contracts)
Contratos de spec.md: Formato A (lote de entrada) y Formato B (paquete de distribución).
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class OpportunityType(str, Enum):
    SUCCESS_STORY = "SUCCESS_STORY"
    LOGRO = "LOGRO"
    FAQ = "FAQ"
    CONSULTA_OPERATIVA = "CONSULTA_OPERATIVA"
    OTRO = "OTRO"


# ─── FORMATO A: lote de interacciones ────────────────────────────────────────

class RawMessageInteraction(BaseModel):
    """Estructura de cada interacción dentro del lote recibido."""
    message_id: str
    source: str = "discord"
    channel: str
    timestamp: str
    autor: str
    tipo_declarado: Optional[str] = None
    texto: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchInputPayload(BaseModel):
    """Esquema de entrada para lotes de interacciones (ej: lote_ejemplo_formato_a.json)."""
    formato_version: str = "1.0"
    origen_comunidad: str
    periodo_referencia: str
    fecha_ingesta: Optional[str] = None
    interacciones: List[RawMessageInteraction]


# ─── FORMATO B: paquete de activos de distribución ───────────────────────────

CAMPOS_POR_FORMATO = {
    "post_linkedin": {"titulo", "copy", "hashtags", "canal_recomendado", "potencial_engagement"},
    "destaque_newsletter": {"seccion", "titular", "resumen"},
    "sugerencia_faq": {"tema", "cuerpo", "origen_descripcion"},
}


class OrigenActivo(BaseModel):
    message_id: str
    opportunity_id: str
    channel: Optional[str] = None
    autor: Optional[str] = None
    message: str
    sentiment: Literal["positive", "neutral", "negative"]
    topics: List[str]
    type: OpportunityType
    score: float = Field(ge=0.0, le=1.0)
    reason: str


class Activo(BaseModel):
    activo_id: str
    formato: Literal["post_linkedin", "destaque_newsletter", "sugerencia_faq"]
    estado_curaduria: Literal["borrador", "aprobado", "publicado", "descartado"]
    origen: OrigenActivo
    contenido: Dict[str, Any]

    @model_validator(mode="after")
    def _contenido_segun_formato(self):
        faltan = CAMPOS_POR_FORMATO[self.formato] - self.contenido.keys()
        if faltan:
            raise ValueError(f"{self.activo_id}: al contenido de {self.formato} le faltan {sorted(faltan)}")
        return self


class Tendencia(BaseModel):
    tema: str
    menciones: int
    descripcion: str


class ResumenComunidad(BaseModel):
    total_interacciones_procesadas: int
    sentimiento_predominante: Optional[str] = None
    distribucion_sentimiento: Dict[str, int]
    temas_principales: List[str]
    oportunidades_detectadas: int
    consultas_operativas: int
    tendencias_detectadas: List[Tendencia]


class AlmacenamientoOCI(BaseModel):
    bucket: str
    ruta_objeto: str
    status: str


class PaqueteDistribucion(BaseModel):
    formato_version: Literal["1.0"]
    status: Literal["exito", "parcial", "error"]
    paquete_id: str
    origen_comunidad: str
    periodo_referencia: str
    fecha_generacion: str
    resumen_comunidad: ResumenComunidad
    activos: List[Activo]
    almacenamiento_oci: AlmacenamientoOCI
