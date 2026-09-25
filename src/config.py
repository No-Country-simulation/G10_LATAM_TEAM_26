"""
CommunityLab AI - Configuración del motor
Proveedores de IA, umbrales y límites. Todo lo configurable se puede sobreescribir desde el .env.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

# langchain-google-genai lee GOOGLE_API_KEY; el proyecto usa GEMINI_API_KEY
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

PROVEEDORES = {
    "gemini": {"key": "GOOGLE_API_KEY",
               "analisis": "gemini-3.5-flash-lite", "redaccion": "gemini-3.5-flash-lite"},
    "groq": {"key": "GROQ_API_KEY",
             "analisis": "openai/gpt-oss-120b", "redaccion": "openai/gpt-oss-120b"},
}
PROVEEDOR = os.getenv("LLM_PROVIDER", "gemini").lower()
RESPALDO = "groq" if PROVEEDOR == "gemini" else "gemini"

TIPOS_OPORTUNIDAD = ("SUCCESS_STORY", "LOGRO", "FAQ", "CONSULTA_OPERATIVA", "OTRO")
UMBRALES_POR_TIPO = {"SUCCESS_STORY": 0.8, "LOGRO": 0.8, "FAQ": 0.7}  # solo estos tipos generan contenido
TEMA_SOCIAL = "social"

# "compacta": una llamada por lote (análisis + clasificación; score y razón solo para candidatos).
# "completa": analista y detector por separado, con score y razón para cada mensaje.
MODO_CLASIFICACION = os.getenv("LLM_CLASIFICACION", "compacta").lower()

TAMANO_LOTE = int(os.getenv("LLM_TAMANO_LOTE", "20"))
# Con 8 piezas por llamada, el JSON de redacción supera lo que Groq valida con json_schema
TAMANO_LOTE_CONTENIDO = int(os.getenv("LLM_TAMANO_LOTE_CONTENIDO", "4"))
MAX_REINTENTOS_CUOTA = 3
# Espera base entre reintentos por cuota (crece x1, x2, x3); bajarla acelera el paso al respaldo
ESPERA_BASE_S = int(os.getenv("LLM_ESPERA_BASE", "30"))
# Más de 3 lotes simultáneos arriesga el límite de tokens por minuto de las capas gratuitas
MAX_CONCURRENCIA = int(os.getenv("LLM_CONCURRENCIA", "3"))

BUCKET_OCI = os.getenv("OCI_BUCKET_NAME", "communitylab-bucket")
DIRECTORIO_SALIDAS = RAIZ / "salidas"
