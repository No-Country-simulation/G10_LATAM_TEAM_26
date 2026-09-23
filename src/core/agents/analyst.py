"""
Agente 1: Community Analyst
Analiza sentimiento, temas y relevancia del mensaje.
"""
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from src.domain.schemas import SemanticAnalysis
from src.utils.logger import setup_logger

logger = setup_logger("analyst_agent")

SYSTEM_PROMPT = """Eres un experto analista semántico de comunidades tecnológicas.
Tu objetivo es analizar mensajes de una comunidad estudiantil y técnica.
Evalúa objetivamente:
1. Sentimiento predominante (positive, neutral, negative).
2. Temas o tecnologías mencionadas (ej: LangChain, OCI, Python, Empleo, etc.).
3. Nivel de relevancia comunicacional o comunitaria (de 0.0 a 1.0).
4. Intención del usuario (compartir logro, duda técnica, feedback, conversación casual).
"""

def analyze_message(clean_text: str, declared_type: str = "") -> SemanticAnalysis:
    """Clasifica semánticamente el mensaje usando Gemini o fallback heurístico."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    
    # Si hay API Key válida, usamos el modelo de IA
    if api_key and api_key != "tu_api_key_aqui":
        try:
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0.1,
                api_key=api_key
            )
            structured_llm = llm.with_structured_output(SemanticAnalysis)
            prompt = f"Tipo declarado: {declared_type}\nMensaje: \"{clean_text}\""
            return structured_llm.invoke([("system", SYSTEM_PROMPT), ("human", prompt)])
        except Exception as e:
            logger.error(f"Fallo al invocar Gemini: {str(e)}. Usando análisis heurístico.")

    # Fallback heurístico inteligente (para desarrollo offline o sin cuota)
    text_lower = clean_text.lower()
    sentiment = "positive" if any(w in text_lower for w in ["logré", "seleccionada", "contrato", "aprobé", "gracias", "genial"]) else "neutral"
    
    topics = []
    for tech in ["langchain", "langgraph", "oci", "python", "docker", "api", "n8n", "sql"]:
        if tech in text_lower:
            topics.append(tech.upper())
    if not topics:
        topics = ["General"]

    relevance = 0.5
    if declared_type in ["testimonio", "logro"]:
        relevance = 0.95
    elif declared_type == "pregunta_tecnica":
        relevance = 0.85
    elif declared_type == "feedback":
        relevance = 0.70

    return SemanticAnalysis(
        sentiment=sentiment,
        topics=topics,
        relevance_score=relevance,
        intent=declared_type
    )