"""
CommunityLab: grafo LangGraph con LLM (Gemini o Groq) para analizar mensajes de la comunidad ONE.

Versión consolidada — base de Gregory + Axel, con 5 injertos:
  1. Modelos por especialidad: flash-lite analiza, 3.8-flash redacta (pareja del benchmark).
  2. Respaldo automático: si el proveedor titular agota reintentos, conmuta a Groq en la misma corrida.
  3. Relleno neutro en TODOS los nodos: un id omitido por el LLM nunca se pierde en silencio.
  4. Modo --simulado (sin API key): heurísticas para desarrollo y demos sin gastar cuota.
  5. formato_version 1.0 (acuerdo del equipo) + acepta GEMINI_API_KEY o GOOGLE_API_KEY.

Requisitos:
    pip install langgraph langchain-google-genai langchain-groq pydantic python-dotenv

Configuración (entorno o archivo .env junto a este script; no lo subas a git):
    LLM_PROVIDER=gemini | groq        (por defecto gemini)
    GOOGLE_API_KEY / GEMINI_API_KEY / GROQ_API_KEY   según el proveedor
    LLM_MODEL_ANALISIS / LLM_MODEL_REDACCION         opcionales, sobreescriben los defaults

Uso:
    python communitylab_agent.py                     # corre el ejemplo
    python communitylab_agent.py lote.json           # JSON con la lista "interacciones"
    python communitylab_agent.py comentarios.csv     # CSV o export de Discord
    python communitylab_agent.py lote.json --simulado  # sin IA, heurísticas (sin cuota)

Salidas (junto al script, carpeta salidas/):
    <paquete_id>.json         paquete final (Formato B)
    <paquete_id>_cuadro.csv   cuadro resumen por mensaje
"""
import csv
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from pydantic import BaseModel, Field

DIRECTORIO = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(DIRECTORIO, ".env"))

# INJERTO 5: langchain-google-genai lee GOOGLE_API_KEY; aceptamos también GEMINI_API_KEY
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# INJERTO 1: un modelo por especialidad (la pareja validada por benchmark).
# Con batching (20 msgs/llamada) la latencia del 3.8 en redacción es tolerable.
PROVEEDORES = {
    "gemini": {"key": "GOOGLE_API_KEY",
               "analisis": "gemini-3.5-flash-lite", "redaccion": "gemini-3.8-flash"},
    "groq": {"key": "GROQ_API_KEY",
             "analisis": "openai/gpt-oss-120b", "redaccion": "openai/gpt-oss-120b"},
}
PROVEEDOR = os.getenv("LLM_PROVIDER", "gemini").lower()
RESPALDO = "groq" if PROVEEDOR == "gemini" else "gemini"

UMBRALES_POR_TIPO = {"SUCCESS_STORY": 0.8, "LOGRO": 0.8, "FAQ": 0.65}  # tipos que generan contenido
TEMA_SOCIAL = "social"
TAMANO_LOTE = 20
TAMANO_LOTE_CONTENIDO = 8
MAX_REINTENTOS_CUOTA = 3
BUCKET_OCI = "communitylab-bucket"
DIRECTORIO_SALIDAS = os.path.join(DIRECTORIO, "salidas")


def _modelo(proveedor: str, rol: str) -> str:
    return os.getenv(f"LLM_MODEL_{rol.upper()}", PROVEEDORES[proveedor][rol])


@lru_cache(maxsize=None)
def _llm(proveedor: str, rol: str, temperature: float):
    variable_key = PROVEEDORES[proveedor]["key"]
    if not os.getenv(variable_key):
        raise RuntimeError(f"Falta {variable_key} para el proveedor '{proveedor}'.")
    modelo = _modelo(proveedor, rol)
    if proveedor == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=modelo, temperature=temperature, max_retries=3)
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=modelo, temperature=temperature, max_retries=3)


def _es_limite_de_cuota(error: Exception) -> bool:
    nombre = type(error).__name__
    return "RateLimit" in nombre or "ResourceExhausted" in nombre \
        or getattr(error, "status_code", None) in (429, 503)


def _invocar(prompt, esquema, rol: str, temperature: float, entrada: Dict[str, Any]):
    """invoke con espera ante cuota/saturación y RESPALDO AUTOMÁTICO (injerto 2):
    si el proveedor titular agota los reintentos, conmuta al alterno en la misma corrida."""
    for proveedor in (PROVEEDOR, RESPALDO):
        if not os.getenv(PROVEEDORES[proveedor]["key"]):
            continue
        cadena = prompt | _llm(proveedor, rol, temperature).with_structured_output(esquema)
        for intento in range(MAX_REINTENTOS_CUOTA + 1):
            try:
                return cadena.invoke(entrada)
            except Exception as error:
                if not _es_limite_de_cuota(error) or intento == MAX_REINTENTOS_CUOTA:
                    if proveedor != RESPALDO:
                        print(f"'{proveedor}' falló ({type(error).__name__}); "
                              f"conmutando a '{RESPALDO}'...", file=sys.stderr)
                        break  # probar el respaldo
                    raise
                espera = 30 * (intento + 1)
                print(f"Cuota de {proveedor} agotada, reintento en {espera}s...", file=sys.stderr)
                time.sleep(espera)
    raise RuntimeError("Ningún proveedor disponible (revisa las API keys del .env).")


def _lotes(items: List[Any], n: int = TAMANO_LOTE):
    for i in range(0, len(items), n):
        yield items[i:i + n]


def _json_mensajes(mensajes: List[Dict[str, Any]], campos: List[str]) -> str:
    return json.dumps([{c: m.get(c) for c in campos} for m in mensajes], ensure_ascii=False)


# 1. Estado del grafo
class AgentState(TypedDict, total=False):
    simulado: bool                                  # modo sin IA (lo fija procesar())
    interacciones_originales: List[Dict[str, Any]]
    metadatos_lote: Dict[str, Any]
    mensajes_analizados: List[Dict[str, Any]]
    clasificaciones: Dict[str, Dict[str, Any]]
    oportunidades: List[Dict[str, Any]]
    activos_generados: List[Dict[str, Any]]
    paquete_final: Dict[str, Any]


# --- ESQUEMAS DE SALIDA ESTRUCTURADA ---

class AnalisisMensaje(BaseModel):
    message_id: str
    sentiment: Literal["positive", "neutral", "negative"]
    topics: List[str] = Field(description="Entre 1 y 4 temas en minúsculas, o solo 'social' si es charla social")
    intencion: str = Field(description="Qué busca el autor, en una frase")


class AnalisisLote(BaseModel):
    mensajes: List[AnalisisMensaje]


class Clasificacion(BaseModel):
    message_id: str
    type: Literal["SUCCESS_STORY", "LOGRO", "FAQ", "CONSULTA_OPERATIVA", "OTRO"]
    score: float = Field(ge=0, le=1, description="Qué tan buena oportunidad de contenido es")
    reason: str = Field(description="Una frase explicando el tipo y el score")


class ClasificacionLote(BaseModel):
    mensajes: List[Clasificacion]


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


# --- MODO SIMULADO (injerto 4): heurísticas sin IA, para desarrollo/demo sin cuota ---

_EXITO = re.compile(r"contrat|seleccionad|firmé|conseguí .*(trabajo|empleo)|primer (trabajo|empleo|contrato)"
                    r"|ascenso|desde el \w+ soy|soy (analista|desarrollador|dev|qa|data)", re.I)
_LOGRO = re.compile(r"certificaci|aprobé|terminé el curso|estrellas en github|gané|finalista", re.I)
_SOCIAL = re.compile(r"felicit|gracias|buenos días|buenas tardes|buenas noches|jaja|😂|🎉|éxitos", re.I)


def _sim_analisis(msg: Dict[str, Any]) -> Dict[str, Any]:
    t = msg["texto"]
    social = bool(_SOCIAL.search(t)) and not _EXITO.search(t)
    return {"sentiment": "positive" if (_EXITO.search(t) or _SOCIAL.search(t)) else "neutral",
            "topics": [TEMA_SOCIAL] if social else ["general"],
            "intencion": "[SIMULADO]", "analisis_ok": True}


def _sim_clasificacion(msg: Dict[str, Any]) -> Dict[str, Any]:
    t = msg["texto"]
    if _EXITO.search(t):
        return {"type": "SUCCESS_STORY", "score": 0.9, "reason": "[SIMULADO] patrón de contratación/logro laboral"}
    if _LOGRO.search(t):
        return {"type": "LOGRO", "score": 0.85, "reason": "[SIMULADO] patrón de logro/certificación"}
    if "?" in t and len(t) > 60 and not _SOCIAL.search(t):
        return {"type": "FAQ", "score": 0.7, "reason": "[SIMULADO] pregunta con contexto"}
    return {"type": "OTRO", "score": 0.1, "reason": "[SIMULADO] charla social o sin contexto"}


# --- NODOS DEL GRAFO ---

from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

PROMPT_ANALISTA = ChatPromptTemplate.from_messages([
    ("system",
     "Eres un analista de comunidades de aprendizaje (CommunityLab) de la comunidad ONE. "
     "Para cada mensaje identifica el sentimiento, sus temas y la intención del autor.\n"
     "Temas: usa temas sustantivos como frases cortas en minúsculas (por ejemplo 'empleo', "
     "'variables de entorno', 'python', 'git', 'entrevistas técnicas', 'clases grabadas', 'plataforma'). "
     "Reutiliza el mismo nombre de tema entre mensajes cuando hablen de lo mismo. Si el mensaje es charla social (saludos, "
     "agradecimientos, felicitaciones, memes, bromas) usa como único tema 'social'.\n"
     "Devuelve exactamente un resultado por cada message_id recibido, sin inventar ids."),
    ("human", "Mensajes (JSON):\n{mensajes}"),
])


def community_analyst(state: AgentState):
    """Nodo 1: sentimiento, temas e intención de cada mensaje."""
    analizados = []
    for lote in _lotes(state["interacciones_originales"]):
        if state.get("simulado"):
            por_id = None
        else:
            resultado = _invocar(PROMPT_ANALISTA, AnalisisLote, "analisis", 0,
                                 {"mensajes": _json_mensajes(lote, ["message_id", "texto", "canal"])})
            por_id = {r.message_id: r for r in (resultado.mensajes if resultado else [])}
        for msg in lote:
            if state.get("simulado"):
                analizados.append({**msg, **_sim_analisis(msg)})
                continue
            r = por_id.get(msg["message_id"])
            analizados.append({
                **msg,
                "sentiment": r.sentiment if r else "neutral",
                "topics": [t.strip().lower() for t in r.topics] if r else [],
                "intencion": r.intencion if r else "",
                "analisis_ok": r is not None,
            })
    return {"mensajes_analizados": analizados}


PROMPT_DETECTOR = ChatPromptTemplate.from_messages([
    ("system",
     "Clasificas mensajes de una comunidad de aprendizaje para detectar oportunidades de contenido.\n"
     "Tipos:\n"
     "- SUCCESS_STORY: el autor consiguió trabajo, fue contratado o seleccionado, o hizo una transición profesional.\n"
     "- LOGRO: el autor terminó un curso, certificación o proyecto destacable.\n"
     "- FAQ: duda técnica o conceptual, con contexto suficiente, cuya respuesta serviría a muchos miembros.\n"
     "- CONSULTA_OPERATIVA: duda logística o puntual sobre clases, grabaciones, links, horarios, accesos, "
     "fallas de la plataforma o del instalador. Su respuesta depende de información interna del programa.\n"
     "- OTRO: todo lo demás, incluyendo charla social, memes, felicitaciones o reacciones a logros ajenos, "
     "anuncios y preguntas sin contexto suficiente para entenderlas.\n"
     "El score (0 a 1) mide qué tan valioso sería convertir el mensaje en contenido público: "
     "claridad, relevancia para la comunidad y potencial inspirador o educativo. Usa scores altos "
     "(>0.8) solo para casos claros. Para CONSULTA_OPERATIVA y OTRO usa scores bajos.\n"
     "Si el mensaje trae 'canal', 'reacciones' o 'respuestas', úsalos como señales adicionales de "
     "contexto e interés de la comunidad.\n"
     "Devuelve exactamente un resultado por cada message_id recibido."),
    ("human", "Mensajes analizados (JSON):\n{mensajes}"),
])

# INJERTO 3: un id que el LLM omite recibe clasificación neutra explícita — nunca desaparece
CLASIFICACION_NEUTRA = {"type": "OTRO", "score": 0.0,
                        "reason": "sin clasificar (el modelo omitió este id); revisar manualmente"}


def opportunity_detector(state: AgentState):
    """Nodo 2: clasifica y puntúa todos los mensajes; filtra oportunidades por umbral del tipo."""
    clasificaciones = {}
    oportunidades = []
    for lote in _lotes(state["mensajes_analizados"]):
        if state.get("simulado"):
            por_id = None
        else:
            entrada = _json_mensajes(lote, ["message_id", "texto", "canal", "reacciones", "respuestas",
                                            "sentiment", "topics", "intencion"])
            resultado = _invocar(PROMPT_DETECTOR, ClasificacionLote, "analisis", 0, {"mensajes": entrada})
            por_id = {c.message_id: c for c in (resultado.mensajes if resultado else [])}
        for msg in lote:
            if state.get("simulado"):
                clasificaciones[msg["message_id"]] = _sim_clasificacion(msg)
            else:
                c = por_id.get(msg["message_id"])
                clasificaciones[msg["message_id"]] = (
                    {"type": c.type, "score": round(c.score, 2), "reason": c.reason}
                    if c else dict(CLASIFICACION_NEUTRA))
            cl = clasificaciones[msg["message_id"]]
            if cl["type"] in UMBRALES_POR_TIPO and cl["score"] >= UMBRALES_POR_TIPO[cl["type"]]:
                oportunidades.append({
                    **msg,
                    **cl,
                    "opportunity_id": f"OPP-{len(oportunidades) + 1:03d}",
                })
    return {"clasificaciones": clasificaciones, "oportunidades": oportunidades}


def hay_oportunidades(state: AgentState) -> str:
    """Decisión: ¿hay oportunidades que pasen el umbral?"""
    return "generar_contenido" if state.get("oportunidades") else "solo_analitica"


FORMATOS_POR_TIPO = {
    "SUCCESS_STORY": ["post_linkedin", "destaque_newsletter"],
    "LOGRO": ["post_linkedin"],
    "FAQ": ["sugerencia_faq"],
}
GUIAS_FORMATO = {
    "post_linkedin": "Post para el LinkedIn oficial. titulo: título atractivo. cuerpo: copy de 80 a 150 "
                     "palabras en párrafos cortos separados por saltos de línea, tono cercano y profesional, "
                     "cierra con una pregunta a la audiencia. Completa hashtags (3 a 5, con #) y "
                     "potencial_engagement (alto, medio o bajo).",
    "destaque_newsletter": "Destacado para el newsletter. titulo: titular de una línea. cuerpo: resumen de "
                           "1 o 2 frases. seccion: 'Logro de la Semana' para historias de éxito.",
    "sugerencia_faq": "Entrada de FAQ. titulo: la pregunta reformulada de forma general, o un 'Tip rápido: ...'. "
                      "cuerpo: respuesta clara y práctica basada en conocimiento técnico general. NUNCA inventes "
                      "datos institucionales del programa (horarios, links, canales, políticas, plazos, nombres "
                      "de secciones o personas); si la respuesta los necesita, escribe [COMPLETAR: qué dato falta]. "
                      "origen_descripcion: una frase sobre de dónde surge la duda.",
}
CANALES = {"post_linkedin": "LinkedIn Oficial"}
PREFIJOS = {"post_linkedin": "POST", "destaque_newsletter": "NEWS", "sugerencia_faq": "FAQ"}

PROMPT_ESTRATEGA = ChatPromptTemplate.from_messages([
    ("system",
     "Eres estratega de contenido de CommunityLab (comunidad ONE). Redactas borradores en español "
     "latinoamericano neutro que un humano revisará antes de publicar. Escribe siempre con la voz "
     "oficial de CommunityLab, en tercera persona sobre el miembro ('una integrante de la comunidad...', "
     "'un estudiante...'), nunca como si fueras el autor del mensaje: prohibido usar la primera persona "
     "singular del autor (compartí, soy, logré, me contrataron) fuera de una cita entre comillas. "
     "No inventes datos que no estén en el mensaje original y no incluyas nombres ni datos personales.\n\n"
     "EJEMPLO DE REFERENCIA (post_linkedin) — imita su estructura, ritmo y tono exactos:\n"
     "---\n"
     "Título: 'De asistente administrativa a Analista de Automatización: el ascenso de una integrante'\n"
     "Copy: 'Hace un año, una integrante de la comunidad era asistente administrativa y no sabía programar.\n\n"
     "Hoy le confirmaron su ascenso a Analista de Automatización.\n\n"
     "¿La clave? Presentó a su empresa tres flujos de automatización con IA que ahorran 20 horas "
     "semanales a su equipo. No fue suerte: fue formación aplicada a problemas reales.\n\n"
     "‘Se puede, de verdad se puede’, escribió a su comunidad de estudio.\n\n"
     "El mejor portfolio es el impacto medible. ¿Qué proyecto tuyo habla mejor de ti?'\n"
     "---\n"
     "Observa del ejemplo: (1) abre con un contraste antes/después en una línea; (2) párrafos de 1-2 "
     "oraciones separados por línea en blanco; (3) UNA cita textual BREVE del miembro entre comillas "
     "(nunca el mensaje completo pegado); (4) moraleja sobria, sin exclamaciones múltiples ni palabras "
     "como 'increíble'; (5) cierra con UNA pregunta directa a la audiencia; (6) hashtags en español.\n\n"
     "Redacta un borrador por cada pieza recibida, respetando su formato, y devuelve el mismo pieza_id.\n"
     "Guías por formato:\n{guias}"),
    ("human", "Piezas a redactar (JSON):\n{piezas}"),
])


def _origen(opp: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "message_id": opp["message_id"],
        "opportunity_id": opp["opportunity_id"],
        "channel": opp.get("canal"),
        "autor": opp.get("autor"),
        "message": opp["texto"],
        "sentiment": opp["sentiment"],
        "topics": opp["topics"],
        "type": opp["type"],
        "score": opp["score"],
        "reason": opp["reason"],
    }


def _contenido(formato: str, b: Borrador) -> Dict[str, Any]:
    if formato == "post_linkedin":
        return {
            "titulo": b.titulo,
            "copy": b.cuerpo,
            "hashtags": [h if h.startswith("#") else f"#{h}" for h in b.hashtags],
            "canal_recomendado": CANALES[formato],
            "potencial_engagement": b.potencial_engagement or "medio",
        }
    if formato == "destaque_newsletter":
        return {"seccion": b.seccion or "Logro de la Semana", "titular": b.titulo, "resumen": b.cuerpo}
    return {"tema": b.titulo, "cuerpo": b.cuerpo, "origen_descripcion": b.origen_descripcion or ""}


def _sim_borrador(pieza: Dict[str, Any]) -> Borrador:
    return Borrador(pieza_id=pieza["pieza_id"],
                    titulo=f"[SIMULADO] {pieza['opp']['texto'][:50]}...",
                    cuerpo="[SIMULADO — con IA real acá va el borrador redactado]",
                    hashtags=["#CommunityLab"], potencial_engagement="medio",
                    seccion="Logro de la Semana", origen_descripcion="[SIMULADO]")


def content_strategist(state: AgentState):
    """Nodo 3: un borrador por cada formato que corresponde al tipo de oportunidad (en lotes)."""
    guias = "\n".join(f"- {f}: {g}" for f, g in GUIAS_FORMATO.items())
    piezas = [
        {"pieza_id": f"{opp['opportunity_id']}:{formato}", "formato": formato, "opp": opp}
        for opp in state["oportunidades"]
        for formato in FORMATOS_POR_TIPO.get(opp["type"], [])
    ]
    contadores = Counter()
    activos = []
    piezas_perdidas = []
    for lote in _lotes(piezas, TAMANO_LOTE_CONTENIDO):
        if state.get("simulado"):
            por_id = {p["pieza_id"]: _sim_borrador(p) for p in lote}
        else:
            entrada = [{"pieza_id": p["pieza_id"], "formato": p["formato"], "tipo": p["opp"]["type"],
                        "canal": p["opp"].get("canal"), "mensaje": p["opp"]["texto"],
                        "temas": p["opp"]["topics"]} for p in lote]
            resultado = _invocar(PROMPT_ESTRATEGA, BorradorLote, "redaccion", 0.4,
                                 {"guias": guias, "piezas": json.dumps(entrada, ensure_ascii=False)})
            por_id = {b.pieza_id: b for b in (resultado.borradores if resultado else [])}
        for pieza in lote:
            borrador = por_id.get(pieza["pieza_id"])
            if not borrador:
                piezas_perdidas.append(pieza["pieza_id"])  # INJERTO 3: se reporta, no se pierde en silencio
                continue
            formato = pieza["formato"]
            contadores[formato] += 1
            activos.append({
                "activo_id": f"{PREFIJOS[formato]}-{contadores[formato]:03d}",
                "formato": formato,
                "estado_curaduria": "borrador",
                "origen": _origen(pieza["opp"]),
                "contenido": _contenido(formato, borrador),
            })
    if piezas_perdidas:
        print(f"AVISO: el modelo omitió {len(piezas_perdidas)} pieza(s): {piezas_perdidas}", file=sys.stderr)
    return {"activos_generados": activos}


NOMBRES_TIPO = {
    "SUCCESS_STORY": ("historia de éxito", "historias de éxito"),
    "LOGRO": ("logro", "logros"),
    "FAQ": ("pregunta técnica", "preguntas técnicas"),
    "CONSULTA_OPERATIVA": ("consulta operativa", "consultas operativas"),
    "OTRO": ("mensaje general", "mensajes generales"),
}


def _tendencias(analizados: List[Dict[str, Any]], clasificaciones: Dict[str, Dict[str, Any]],
                periodo: str) -> List[Dict[str, Any]]:
    """Temas sustantivos con 2 o más menciones, con el desglose por tipo de mensaje."""
    por_tema: Dict[str, Counter] = {}
    for m in analizados:
        tipo = clasificaciones.get(m["message_id"], {}).get("type", "OTRO")
        for tema in set(m["topics"]) - {TEMA_SOCIAL}:
            por_tema.setdefault(tema, Counter())[tipo] += 1
    tendencias = []
    for tema, tipos in sorted(por_tema.items(), key=lambda kv: -sum(kv[1].values()))[:5]:
        menciones = sum(tipos.values())
        if menciones < 2:
            continue
        detalle = ", ".join(f"{n} {NOMBRES_TIPO[t][0 if n == 1 else 1]}" for t, n in tipos.most_common())
        tendencias.append({
            "tema": tema,
            "menciones": menciones,
            "descripcion": f"{menciones} mensajes sobre {tema} en {periodo.replace('_', ' ').lower()} ({detalle})",
        })
    return tendencias


def empaquetar(state: AgentState):
    """Nodo 4: resumen, tendencias y activos en el JSON final."""
    analizados = state.get("mensajes_analizados", [])
    clasificaciones = state.get("clasificaciones", {})
    metadatos = state.get("metadatos_lote", {})
    ahora = datetime.now(timezone.utc)
    anio, semana_iso, _ = ahora.isocalendar()
    periodo = metadatos.get("periodo_referencia") or f"Semana_{semana_iso:02d}"
    numero_semana = int(re.search(r"\d+", periodo).group()) if re.search(r"\d+", periodo) else semana_iso
    # id por timestamp: único sin leer el filesystem (procesar() se mantiene pura)
    paquete_id = f"PKG-{anio}-S{numero_semana:02d}-{ahora.strftime('%H%M%S')}"

    sentimiento = Counter(m["sentiment"] for m in analizados)
    temas = Counter(t for m in analizados for t in m["topics"] if t != TEMA_SOCIAL)

    paquete_final = {
        "formato_version": "1.0",  # INJERTO 5: acuerdo del equipo — todo en 1.0
        "status": "exito",
        "paquete_id": paquete_id,
        "origen_comunidad": metadatos.get("origen_comunidad", "desconocido"),
        "periodo_referencia": periodo,
        "fecha_generacion": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "resumen_comunidad": {
            "total_interacciones_procesadas": len(state["interacciones_originales"]),
            "sentimiento_predominante": sentimiento.most_common(1)[0][0] if sentimiento else None,
            "distribucion_sentimiento": {s: sentimiento.get(s, 0) for s in ("positive", "neutral", "negative")},
            "temas_principales": [t for t, _ in temas.most_common(5)],
            "oportunidades_detectadas": len(state.get("oportunidades", [])),
            "consultas_operativas": sum(1 for c in clasificaciones.values() if c["type"] == "CONSULTA_OPERATIVA"),
            "tendencias_detectadas": _tendencias(analizados, clasificaciones, periodo),
        },
        "activos": state.get("activos_generados", []),
        "almacenamiento_oci": {
            "bucket": BUCKET_OCI,
            "ruta_objeto": f"generated/{ahora:%Y-%m-%d}/{paquete_id}.json",
            "status": "pendiente",  # cambiar a "guardado_con_exito" cuando exista la subida real
        },
    }
    return {"paquete_final": paquete_final}


# --- CONSTRUCCIÓN DEL GRAFO ---

workflow = StateGraph(AgentState)
workflow.add_node("community_analyst", community_analyst)
workflow.add_node("opportunity_detector", opportunity_detector)
workflow.add_node("content_strategist", content_strategist)
workflow.add_node("empaquetar", empaquetar)

workflow.set_entry_point("community_analyst")
workflow.add_edge("community_analyst", "opportunity_detector")
workflow.add_conditional_edges(
    "opportunity_detector",
    hay_oportunidades,
    {
        "generar_contenido": "content_strategist",  # Sí
        "solo_analitica": "empaquetar",             # No
    },
)
workflow.add_edge("content_strategist", "empaquetar")
workflow.add_edge("empaquetar", END)

app = workflow.compile()


# --- ENTRADA ---

def _limpiar_discord(texto: str) -> str:
    """Reemplaza menciones de Discord (<@id>, <@&id>, <#id>) para no enviar IDs al LLM."""
    texto = re.sub(r"<@&\d+>", "@rol", texto)
    texto = re.sub(r"<@!?\d+>", "@usuario", texto)
    return re.sub(r"<#\d+>", "#canal", texto).strip()


def _normalizar_fila(fila: Dict[str, str], indice: int) -> Dict[str, Any]:
    if "texto" in fila:  # Formato A: message_id, texto
        return {"message_id": fila.get("message_id") or f"csv-{indice:04d}", "texto": (fila["texto"] or "").strip()}
    # Export de Discord: AuthorID, Author, Date, Content, Attachments, Reactions
    return {
        "message_id": f"discord-{indice:04d}",
        "texto": _limpiar_discord(fila.get("Content") or ""),
        "fecha": (fila.get("Date") or "")[:19],
        "autor": fila.get("Author"),  # no se envía al LLM
        "reacciones": sum(int(n) for n in re.findall(r"\((\d+)\)", fila.get("Reactions") or "")),
    }


def cargar_csv(ruta: str):
    """Lee un CSV con columnas message_id/texto o un export de Discord; descarta filas sin texto."""
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        filas = [_normalizar_fila(fila, i) for i, fila in enumerate(csv.DictReader(f), start=1)]
    return [fila for fila in filas if fila["texto"]], {}


def cargar_json(ruta: str):
    """Lee un lote JSON con la lista 'interacciones' (message_id, texto, channel, metadata...)."""
    with open(ruta, encoding="utf-8-sig") as f:
        datos = json.load(f)
    interacciones = []
    for i, item in enumerate(datos.get("interacciones", []), start=1):
        metadata = item.get("metadata") or {}
        interacciones.append({
            "message_id": item.get("message_id") or f"json-{i:04d}",
            "texto": (item.get("texto") or "").strip(),
            "canal": item.get("channel"),
            "fecha": item.get("timestamp"),
            "autor": item.get("autor"),  # no se envía al LLM
            "reacciones": metadata.get("reacciones", 0),
            "respuestas": metadata.get("respuestas", 0),
        })
    metadatos = {k: datos[k] for k in ("origen_comunidad", "periodo_referencia") if datos.get(k)}
    return [m for m in interacciones if m["texto"]], metadatos


def cargar_entrada(ruta: str):
    return cargar_json(ruta) if ruta.lower().endswith(".json") else cargar_csv(ruta)


# --- SALIDA ---

def cuadro_resumen(resultado: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Una fila por mensaje procesado con su clasificación y los activos que generó."""
    activos_por_mensaje: Dict[str, Dict[str, List[str]]] = {}
    for a in resultado.get("activos_generados", []):
        activos_por_mensaje.setdefault(a["origen"]["message_id"], {}).setdefault(a["formato"], []).append(a["activo_id"])
    filas = []
    for m in resultado["mensajes_analizados"]:
        c = resultado.get("clasificaciones", {}).get(m["message_id"], {})
        activos = activos_por_mensaje.get(m["message_id"], {})
        filas.append({
            "message_id": m["message_id"],
            "canal": m.get("canal") or "",
            "texto": m["texto"],
            "sentimiento": m["sentiment"],
            "tipo": c.get("type", ""),
            "score": c.get("score", ""),
            "contenido_exito": ", ".join(activos.get("post_linkedin", [])),
            "newsletter": ", ".join(activos.get("destaque_newsletter", [])),
            "pregunta_faq": ", ".join(activos.get("sugerencia_faq", [])),
            "reason": c.get("reason", ""),
        })
    return filas


# --- API PÚBLICA: lo que Streamlit, el bot y el CLI importan ---

def procesar(interacciones: List[Dict[str, Any]], metadatos: Optional[Dict[str, Any]] = None,
             simulado: bool = False) -> Dict[str, Any]:
    """Punto de entrada del motor: lista de mensajes -> paquete (Formato B).

    Sirve para lote (N mensajes) y tiempo real (lista de 1). Es una función pura
    de procesamiento: NO escribe archivos — guardar es decisión del que llama
    (el CLI, el panel, o el módulo de storage). Con simulado=True corre con
    heurísticas, sin llamadas a la IA (desarrollo/pruebas sin cuota).
    """
    resultado = app.invoke({"interacciones_originales": interacciones,
                            "metadatos_lote": metadatos or {},
                            "simulado": simulado})
    return resultado["paquete_final"]


def procesar_archivo(ruta: str) -> Dict[str, Any]:
    """Conveniencia: carga un CSV / JSON / export de Discord y lo procesa."""
    interacciones, metadatos = cargar_entrada(ruta)
    return procesar(interacciones, metadatos)


def guardar_salidas(paquete: Dict[str, Any],
                    resultado_completo: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Escribe el paquete JSON (y el cuadro CSV si se pasa el resultado completo)."""
    os.makedirs(DIRECTORIO_SALIDAS, exist_ok=True)
    ruta_paquete = os.path.join(DIRECTORIO_SALIDAS, f"{paquete['paquete_id']}.json")
    with open(ruta_paquete, "w", encoding="utf-8") as f:
        json.dump(paquete, f, indent=2, ensure_ascii=False)
    rutas = {"paquete": ruta_paquete}
    if resultado_completo:
        ruta_cuadro = os.path.join(DIRECTORIO_SALIDAS, f"{paquete['paquete_id']}_cuadro.csv")
        filas = cuadro_resumen(resultado_completo)
        with open(ruta_cuadro, "w", encoding="utf-8-sig", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=list(filas[0].keys()) if filas else ["message_id"])
            escritor.writeheader()
            escritor.writerows(filas)
        rutas["cuadro"] = ruta_cuadro
    return rutas


if __name__ == "__main__":
    # Consolas de Windows usan cp1252 y rompen con emojis de los mensajes
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    simulado = "--simulado" in sys.argv
    argumentos = [a for a in sys.argv[1:] if not a.startswith("--")]
    if argumentos:
        interacciones, metadatos = cargar_entrada(argumentos[0])
    else:
        metadatos = {}
        interacciones = [
            {"message_id": "csv-comentarios-0001",
             "texto": "Comunidad, quedé seleccionada para el puesto de Desarrolladora Junior de IA!"},
            {"message_id": "csv-comentarios-0002",
             "texto": "Tengo una duda: ¿cómo despliego un grafo de LangGraph en OCI Functions?"},
            {"message_id": "csv-comentarios-0003",
             "texto": "Buenas noches a todos"},
        ]

    if simulado:
        print("MODO SIMULADO: sin llamadas a la IA (heurísticas de desarrollo).", file=sys.stderr)

    resultado = app.invoke({"interacciones_originales": interacciones, "metadatos_lote": metadatos,
                            "simulado": simulado})
    paquete = resultado["paquete_final"]
    rutas = guardar_salidas(paquete, resultado)

    print(json.dumps(paquete, indent=2, ensure_ascii=False))
    print(f"\nPaquete: {rutas['paquete']}\nCuadro:  {rutas.get('cuadro', '')}", file=sys.stderr)
