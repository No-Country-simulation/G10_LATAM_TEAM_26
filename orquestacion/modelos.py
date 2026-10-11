"""
Modelos Pydantic de los Formatos de datos (ver spec.md).

Validan lo que entra (Formato A) y lo que sale (Formato B) del pipeline.
Si un JSON no cumple, Pydantic explota con un error claro que dice
exactamente qué campo está mal — eso es intencional: mejor romper acá
que arrastrar datos malformados por todo el sistema.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─────────────────────────── FORMATO A (entrada) ───────────────────────────

class MetadataInteraccion(BaseModel):
    reacciones: int = 0
    respuestas: int = 0


class Interaccion(BaseModel):
    message_id: str
    source: Literal["discord", "slack", "forum", "form", "csv", "json"]
    channel: str
    timestamp: datetime
    autor: str
    # Pista OPCIONAL sobre el tipo de mensaje. Ingesta puede omitirlo (default
    # "otro") o llenarlo solo cuando es obvio y gratis (ej.: canal "logros" ->
    # "logro"). NO es una clasificación: la clasificación real la hace el
    # Opportunity Detector (opportunity.type). Heredado del ejemplo del brief.
    tipo_declarado: Literal[
        "testimonio", "pregunta_tecnica", "feedback", "logro", "conversacion", "otro"
    ] = "otro"
    texto: str = Field(min_length=10)
    metadata: MetadataInteraccion = MetadataInteraccion()


class LoteFormatoA(BaseModel):
    formato_version: str = "1.0"
    origen_comunidad: str
    periodo_referencia: str
    fecha_ingesta: datetime
    interacciones: list[Interaccion] = Field(min_length=1)


# ────────────────────── FORMATO P (interno, análisis) ──────────────────────

class Tracking(BaseModel):
    message_id: str
    source: str
    channel: str
    timestamp: datetime


class Analysis(BaseModel):
    sentiment: Literal["positive", "neutral", "negative"]
    topics: list[str] = Field(min_length=1, max_length=5)
    intent: str
    relevance_score: float = Field(ge=0.0, le=1.0)


class Opportunity(BaseModel):
    opportunity_id: str
    type: Literal["SUCCESS_STORY", "FAQ", "TREND", "FEEDBACK", "MILESTONE", "NONE"]
    opportunity_score: float = Field(ge=0.0, le=1.0)
    reason: str


class Procesado(BaseModel):
    tracking: Tracking
    analysis: Analysis
    opportunity: Opportunity


# ─────────────────────────── FORMATO B v1.1 (salida) ───────────────────────

class Origen(BaseModel):
    """Todo lo que la UI necesita saber del mensaje que dio origen a la pieza —
    autocontenido: el panel no busca en ningún otro archivo (aporte del formato
    de Anthony fusionado al spec)."""
    message_id: str
    opportunity_id: str
    channel: str
    autor: str
    message: str
    sentiment: Literal["positive", "neutral", "negative"]
    topics: list[str]
    type: Literal["SUCCESS_STORY", "FAQ", "TREND", "FEEDBACK", "MILESTONE", "NONE"]
    score: float = Field(ge=0.0, le=1.0)
    reason: str


class Activo(BaseModel):
    activo_id: str
    formato: Literal["post_linkedin", "destaque_newsletter", "sugerencia_faq"]
    estado_curaduria: Literal["borrador", "aprobado", "publicado", "descartado"] = "borrador"
    origen: Origen
    contenido: dict  # estructura según formato — ver spec.md / fixture B


class Tendencia(BaseModel):
    tema: str
    menciones: int
    descripcion: str


class ResumenComunidad(BaseModel):
    total_interacciones_procesadas: int
    sentimiento_predominante: str
    distribucion_sentimiento: dict[str, int]
    temas_principales: list[str]
    oportunidades_detectadas: int
    tendencias_detectadas: list[Tendencia] = []


class AlmacenamientoOCI(BaseModel):
    bucket: str
    ruta_objeto: str
    status: str


class PaqueteFormatoB(BaseModel):
    formato_version: str = "1.0"
    status: Literal["exito", "parcial", "error"]
    paquete_id: str
    origen_comunidad: str
    periodo_referencia: str
    fecha_generacion: datetime
    resumen_comunidad: ResumenComunidad
    activos: list[Activo]
    almacenamiento_oci: Optional[AlmacenamientoOCI] = None
