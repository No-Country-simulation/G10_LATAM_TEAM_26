"""
Agente 1: Community Analyst
Analiza sentimiento, temas y relevancia. Incluye Failover de Modelos para Rate Limits (429).
"""
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from src.domain.schemas import SemanticAnalysis
from src.utils.logger import setup_logger

load_dotenv()
logger = setup_logger("analyst_agent")

SYSTEM_PROMPT = """Eres un experto analista semántico de comunidades tecnológicas.
Tu objetivo es analizar mensajes de una comunidad estudiantil y técnica.
Evalúa:
1. Sentimiento predominante (positive, neutral, negative).
2. Temas o tecnologías mencionadas (LangChain, OCI, Python, Empleo, etc.).
3. Nivel de relevancia comunicacional (0.0 a 1.0).
4. Intención del usuario (compartir logro, duda técnica, feedback, casual).
"""


def _invoke_gemini(model_name: str, api_key: str, text: str, declared_type: str) -> SemanticAnalysis:
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        api_key=api_key
    )
    structured_llm = llm.with_structured_output(SemanticAnalysis)
    prompt = f"Tipo declarado: {declared_type}\nMensaje a evaluar:\n\"{text}\""
    return structured_llm.invoke([("system", SYSTEM_PROMPT), ("human", prompt)])


def analyze_message(clean_text: str, declared_type: str = "") -> SemanticAnalysis:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if api_key and api_key != "tu_api_key_aqui":
        # Lista de modelos ordenados por disponibilidad de cuota
        modelos_candidatos = [
            os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip(),
            "gemini-1.5-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro"
        ]
        
        # Eliminar duplicados manteniendo orden
        modelos_unicos = list(dict.fromkeys(modelos_candidatos))

        for model in modelos_unicos:
            try:
                return _invoke_gemini(model, api_key, clean_text, declared_type)
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    logger.warning(f"Cuota agotada en {model}. Intentando siguiente modelo...")
                    continue
                else:
                    logger.error(f"Error con modelo {model}: {err_msg}")
                    break

    # Fallback heurístico si se agotan las cuotas del día
    text_lower = clean_text.lower()
    sentiment = "positive" if any(w in text_lower for w in ["logré", "seleccionada", "contrato", "aprobé", "gracias", "genial", "empecé", "trabajo"]) else "neutral"

    topics = []
    for tech in ["langchain", "langgraph", "oci", "python", "docker", "api", "n8n", "sql"]:
        if tech in text_lower:
            topics.append(tech.upper())
    if not topics:
        topics = ["General"]

    relevance = 0.50
    if declared_type in ["testimonio", "logro"] or "trabajo" in text_lower or "contrat" in text_lower:
        relevance = 0.95
    elif declared_type == "pregunta_tecnica" or "?" in clean_text or "¿" in clean_text:
        relevance = 0.85
    elif declared_type == "feedback":
        relevance = 0.70

    return SemanticAnalysis(
        sentiment=sentiment,
        topics=topics,
        relevance_score=relevance,
        intent=declared_type or "general"
    )