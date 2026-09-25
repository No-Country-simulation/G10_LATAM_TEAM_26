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
# Modelos alternos de Gemini (misma key, cuota propia por modelo) que se prueban antes de pasar al otro proveedor.
# Elegidos por respuesta y precisión en la tarea de clasificación con 20 mensajes etiquetados.
ALTERNOS_GEMINI = [m.strip() for m in os.getenv("LLM_GEMINI_ALTERNOS", "gemini-3-flash-preview,gemini-2.5-flash")
                   .split(",") if m.strip()]

TIPOS_OPORTUNIDAD = ("SUCCESS_STORY", "MILESTONE", "FAQ", "OPERATIONAL_QUERY", "FEEDBACK", "NONE")
UMBRALES_POR_TIPO = {"SUCCESS_STORY": 0.8, "MILESTONE": 0.8, "FAQ": 0.7}  # solo estos tipos generan contenido
TEMA_SOCIAL = "social"

# "compacta": una llamada por lote (análisis + clasificación; score y razón solo para candidatos).
# "completa": analista y detector por separado, con score y razón para cada mensaje.
MODO_CLASIFICACION = os.getenv("LLM_CLASIFICACION", "compacta").lower()

# Lotes de 10: el primero responde antes y el panel empieza a mostrar mensajes mientras llegan los demás
TAMANO_LOTE = int(os.getenv("LLM_TAMANO_LOTE", "10"))
# Con 8 piezas por llamada, el JSON de redacción supera lo que Groq valida con json_schema
TAMANO_LOTE_CONTENIDO = int(os.getenv("LLM_TAMANO_LOTE_CONTENIDO", "4"))
MAX_REINTENTOS_CUOTA = 3
# Espera base entre reintentos por cuota (crece x1, x2, x3); bajarla acelera el paso al respaldo
ESPERA_BASE_S = int(os.getenv("LLM_ESPERA_BASE", "30"))
# Más de 3 lotes simultáneos arriesga el límite de tokens por minuto de las capas gratuitas
MAX_CONCURRENCIA = int(os.getenv("LLM_CONCURRENCIA", "3"))
# Llamada de cobertura: si el titular no respondió en estos segundos, se lanza la misma llamada al respaldo
# y se usa la primera que llegue (0 la desactiva). Solo para la clasificación, que es lo que el usuario espera.
COBERTURA_S = float(os.getenv("LLM_COBERTURA_S", "10"))
ROLES_CON_COBERTURA = ("analisis",)
# Esfuerzo de razonamiento de gpt-oss en Groq para clasificar: 'low' tarda ~40 % menos y gasta la mitad de cuota
RAZONAMIENTO_GROQ = os.getenv("LLM_RAZONAMIENTO_GROQ", "low")
# Caché de clasificaciones por mensaje: un mensaje ya clasificado con el mismo prompt no vuelve a la IA
USAR_CACHE = os.getenv("LLM_CACHE", "1") == "1"
ARCHIVO_CACHE = RAIZ / "data" / "cache" / "clasificaciones.json"

BUCKET_OCI = os.getenv("OCI_BUCKET_NAME", "communitylab-bucket")
DIRECTORIO_SALIDAS = RAIZ / "salidas"
