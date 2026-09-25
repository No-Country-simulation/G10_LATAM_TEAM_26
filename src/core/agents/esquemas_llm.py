"""
CommunityLab AI - Esquemas de salida estructurada de la IA
Lo que cada agente le pide al modelo (se validan con Pydantic antes de entrar al grafo).
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AnalisisMensaje(BaseModel):
    message_id: str
    sentiment: Literal["positive", "neutral", "negative"]
    topics: List[str] = Field(description="Entre 1 y 4 temas en minúsculas, o solo 'social' si es charla social")
    intencion: str = Field(description="Qué busca el autor, en una frase")


class AnalisisLote(BaseModel):
    mensajes: List[AnalisisMensaje]


class Clasificacion(BaseModel):
    message_id: str
    type: Literal["SUCCESS_STORY", "MILESTONE", "FAQ", "OPERATIONAL_QUERY", "FEEDBACK", "NONE"]
    score: float = Field(ge=0, le=1, description="Qué tan buena oportunidad de contenido es")
    reason: str = Field(description="Una frase explicando el tipo y el score")


class ClasificacionLote(BaseModel):
    mensajes: List[Clasificacion]


class ClasificacionBreve(BaseModel):
    message_id: str
    sentiment: Literal["positive", "neutral", "negative"]
    topics: List[str] = Field(description="1 a 3 temas en minúsculas, o solo 'social' si es charla social")
    type: Literal["SUCCESS_STORY", "MILESTONE", "FAQ", "OPERATIONAL_QUERY", "FEEDBACK", "NONE"]


class Candidato(BaseModel):
    message_id: str
    score: float = Field(ge=0, le=1, description="Qué tan buena oportunidad de contenido es")
    reason: str = Field(description="Una frase explicando el tipo y el score")


class ClasificacionCompacta(BaseModel):
    mensajes: List[ClasificacionBreve]
    candidatos: List[Candidato] = Field(
        default_factory=list, description="Solo mensajes SUCCESS_STORY, MILESTONE o FAQ que podrían ser contenido")


class Borrador(BaseModel):
    pieza_id: str
    titulo: str = Field(description="post: título; newsletter: titular; faq: pregunta general")
    cuerpo: str = Field(description="post: copy; newsletter: resumen; faq: respuesta")
    hashtags: List[str] = Field(default_factory=list, description="Solo post_linkedin: 3 a 5 hashtags")
    potencial_engagement: Optional[Literal["alto", "medio", "bajo"]] = Field(
        default=None, description="Solo post_linkedin")
    seccion: Optional[str] = Field(default=None, description="Solo destaque_newsletter")
    origen_descripcion: Optional[str] = Field(default=None, description="Solo sugerencia_faq")


class BorradorLote(BaseModel):
    borradores: List[Borrador]
