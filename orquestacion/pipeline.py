"""
Pipeline de CommunityLab — grafo LangGraph con la arquitectura multiagente
de la especificación técnica (sección 4):

    community_analyst ──> opportunity_detector ──┬─(hay oportunidades)─> content_strategist ──> empaquetar
    (SIMULADO)            (SIMULADO + reglas)    └─(solo analítica)────────────────────────────> empaquetar

La condición del Opportunity Score es una ARISTA CONDICIONAL real del grafo
(se ve en el diagrama autogenerado). Los nodos SIMULADOS no llaman a la IA:
leen respuestas ya hechas desde data/fixtures/. En la semana 2 se reemplazan
por las llamadas reales a Gemini — buscar los "TODO semana 2".

Uso:
    python -m orquestacion.pipeline data/fixtures/lote_ejemplo_formato_a.json
"""

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from orquestacion.modelos import LoteFormatoA, PaqueteFormatoB, Procesado
from orquestacion.scoring import decidir_formatos

_BASE = Path(__file__).resolve().parent.parent
_FIXTURE_P = _BASE / "data" / "fixtures" / "procesados_ejemplo_formato_p.json"


# ─────────────────────────── Estado del grafo ───────────────────────────
# El "paquete de trabajo" que viaja de nodo en nodo. Cada nodo lee lo que
# necesita y agrega su resultado.

class EstadoPipeline(TypedDict):
    lote: dict            # Formato A (entrada)
    procesados: list      # Formato P por mensaje (analyst + detector lo completan)
    plan: list            # [(procesado, [formatos a generar])] (lo agrega el detector)
    activos: list         # borradores generados (los agrega content_strategist)
    paquete: dict         # Formato B final (lo agrega `empaquetar`)


# ─────────────────────────────── Nodos ──────────────────────────────────

def _respuestas_fixture() -> dict:
    return {
        p["tracking"]["message_id"]: p
        for p in json.loads(_FIXTURE_P.read_text(encoding="utf-8"))["procesados"]
    }


def community_analyst(estado: EstadoPipeline) -> dict:
    """AGENTE 1 (SIMULADO) — Entrada: mensaje limpio. Salida: metadata semántica
    (sentimiento, temas, intención, relevancia).

    Hoy busca el análisis ya hecho en el fixture P por message_id.
    TODO semana 2: reemplazar por la llamada real a Gemini con el prompt Analista.
    """
    respuestas = _respuestas_fixture()
    procesados = []
    for interaccion in estado["lote"]["interacciones"]:
        msg_id = interaccion["message_id"]
        if msg_id in respuestas:
            analysis = respuestas[msg_id]["analysis"]
        else:
            # Mensaje que el fixture no conoce: análisis neutro de relleno,
            # así el pipeline no explota con datos nuevos.
            analysis = {
                "sentiment": "neutral",
                "topics": ["sin_analizar"],
                "intent": "desconocido",
                "relevance_score": 0.0,
            }
        procesados.append({
            "tracking": {
                "message_id": msg_id,
                "source": interaccion["source"],
                "channel": interaccion["channel"],
                "timestamp": interaccion["timestamp"],
            },
            "analysis": analysis,
        })
    return {"procesados": procesados}


def opportunity_detector(estado: EstadoPipeline) -> dict:
    """AGENTE 2 (SIMULADO + reglas REALES) — Entrada: mensaje + metadata.
    Clasifica el tipo de oportunidad, calcula el Opportunity Score y arma el
    plan de generación aplicando los umbrales de scoring.py.

    TODO semana 2: reemplazar la parte simulada por el prompt Detector.
    """
    respuestas = _respuestas_fixture()
    procesados, plan = [], []
    for p in estado["procesados"]:
        msg_id = p["tracking"]["message_id"]
        if msg_id in respuestas:
            opportunity = respuestas[msg_id]["opportunity"]
        else:
            opportunity = {
                "opportunity_id": f"OPP-{msg_id[-4:]}",
                "type": "NONE",
                "opportunity_score": 0.0,
                "reason": "Mensaje fuera del fixture (mock); pendiente de análisis real.",
            }
        procesado = {**p, "opportunity": opportunity}
        Procesado.model_validate(procesado)  # el mock también respeta el Formato P
        procesados.append(procesado)
        formatos = decidir_formatos(opportunity["type"], opportunity["opportunity_score"])
        if formatos:
            plan.append((procesado, formatos))
    return {"procesados": procesados, "plan": plan}


def hay_oportunidades(estado: EstadoPipeline) -> str:
    """ARISTA CONDICIONAL — la flecha "(Si Score >= 0.70)" de la especificación:
    con oportunidades en el plan se genera contenido; sin ellas, directo al paquete."""
    return "generar_contenido" if estado["plan"] else "solo_analitica"


_PLANTILLAS = {
    # TODO semana 2: reemplazar por el prompt Estratega (Tarea 4).
    # Estas plantillas producen contenido esquemático pero con la ESTRUCTURA
    # exacta del Formato B, para que panel y storage trabajen con datos válidos.
    "post_linkedin": lambda p: {
        "titulo": f"[MOCK] Historia de la comunidad: {p['analysis']['topics'][0]}",
        "copy": f"[MOCK — lo redactará Gemini] Basado en: {p['opportunity']['reason']}",
        "hashtags": ["#ComunidadTech", "#MockData"],
        "canal_recomendado": "LinkedIn Oficial",
        "potencial_engagement": "alto" if p["opportunity"]["opportunity_score"] >= 0.9 else "medio",
    },
    "destaque_newsletter": lambda p: {
        "seccion": "Destacado de la Semana",
        "titular": f"[MOCK] {p['opportunity']['reason'][:80]}",
        "resumen": "[MOCK — lo redactará Gemini]",
    },
    "sugerencia_faq": lambda p: {
        "tema": f"[MOCK] Guía sobre: {', '.join(p['analysis']['topics'][:2])}",
        "cuerpo": "[MOCK — lo redactará Gemini]",
        "origen_descripcion": p["opportunity"]["reason"],
    },
}

_PREFIJO_ID = {"post_linkedin": "POST", "destaque_newsletter": "NEWS", "sugerencia_faq": "FAQ"}


def content_strategist(estado: EstadoPipeline) -> dict:
    """AGENTE 3 (SIMULADO) — Entrada: oportunidad + contexto. Adapta el contenido
    al formato y tono del canal objetivo (borradores LinkedIn / Newsletter / FAQ).

    Hoy usa plantillas con la estructura correcta del Formato B.
    TODO semana 2: reemplazar por el prompt Estratega real (Tarea 4).
    """
    # lookup del mensaje original para embeber el origen completo (Formato B v1.1)
    interacciones = {i["message_id"]: i for i in estado["lote"]["interacciones"]}
    activos = []
    contadores: Counter = Counter()
    for procesado, formatos in estado["plan"]:
        msg_id = procesado["tracking"]["message_id"]
        interaccion = interacciones.get(msg_id, {})
        origen = {
            "message_id": msg_id,
            "opportunity_id": procesado["opportunity"]["opportunity_id"],
            "channel": procesado["tracking"]["channel"],
            "autor": interaccion.get("autor", "desconocido"),
            "message": interaccion.get("texto", ""),
            "sentiment": procesado["analysis"]["sentiment"],
            "topics": procesado["analysis"]["topics"],
            "type": procesado["opportunity"]["type"],
            "score": procesado["opportunity"]["opportunity_score"],
            "reason": procesado["opportunity"]["reason"],
        }
        for formato in formatos:
            contadores[formato] += 1
            activos.append({
                "activo_id": f"{_PREFIJO_ID[formato]}-{contadores[formato]:03d}",
                "formato": formato,
                "estado_curaduria": "borrador",
                "origen": origen,
                "contenido": _PLANTILLAS[formato](procesado),
            })
    return {"activos": activos}


def nodo_empaquetar(estado: EstadoPipeline) -> dict:
    """REAL: consolida todo en el paquete final (Formato B) y lo valida."""
    lote, procesados = estado["lote"], estado["procesados"]

    sentimientos = Counter(p["analysis"]["sentiment"] for p in procesados)
    temas = Counter(t for p in procesados for t in p["analysis"]["topics"] if t != "sin_analizar")
    oportunidades = [p for p in procesados if p["opportunity"]["type"] != "NONE"
                     and p["opportunity"]["opportunity_score"] >= 0.70]

    # Tendencias por AGREGACIÓN (código, no IA): un tema repetido en 4+ mensajes
    # del lote es noticia en sí mismo — el caso 3 de la demo.
    UMBRAL_TENDENCIA = 4
    tendencias = [
        {"tema": tema, "menciones": n,
         "descripcion": f"{n} mensajes sobre '{tema}' en el período — conviene publicar una guía o aviso"}
        for tema, n in temas.most_common(5) if n >= UMBRAL_TENDENCIA
    ]

    ahora = datetime.now(timezone.utc)
    periodo = lote["periodo_referencia"].replace("Semana_", "S")
    paquete = {
        "formato_version": "1.0",
        "status": "exito",
        "paquete_id": f"PKG-{ahora.year}-{periodo}-{ahora.strftime('%H%M%S')}",
        "origen_comunidad": lote["origen_comunidad"],
        "periodo_referencia": lote["periodo_referencia"],
        "fecha_generacion": ahora.isoformat(),
        "resumen_comunidad": {
            "total_interacciones_procesadas": len(procesados),
            "sentimiento_predominante": sentimientos.most_common(1)[0][0],
            "distribucion_sentimiento": dict(sentimientos),
            "temas_principales": [t for t, _ in temas.most_common(4)],
            "oportunidades_detectadas": len(oportunidades),
            "tendencias_detectadas": tendencias,
        },
        "activos": estado["activos"],
        "almacenamiento_oci": None,  # lo completa storage/cliente.py al guardar
    }
    PaqueteFormatoB.model_validate(paquete)  # si algo está mal, explota ACÁ
    return {"paquete": paquete}


# ─────────────────────────── Construcción del grafo ───────────────────────

def construir_grafo():
    grafo = StateGraph(EstadoPipeline)
    grafo.add_node("community_analyst", community_analyst)
    grafo.add_node("opportunity_detector", opportunity_detector)
    grafo.add_node("content_strategist", content_strategist)
    grafo.add_node("empaquetar", nodo_empaquetar)

    grafo.add_edge(START, "community_analyst")
    grafo.add_edge("community_analyst", "opportunity_detector")
    # La flecha "(Si Score >= 0.70)" de la especificación, como arista real:
    grafo.add_conditional_edges(
        "opportunity_detector",
        hay_oportunidades,
        {
            "generar_contenido": "content_strategist",  # hay oportunidades sobre el umbral
            "solo_analitica": "empaquetar",             # lote sin oportunidades: directo al paquete
        },
    )
    grafo.add_edge("content_strategist", "empaquetar")
    grafo.add_edge("empaquetar", END)
    return grafo.compile()


def procesar_lote(lote: dict) -> dict:
    """Punto de entrada del pipeline: lote (Formato A) -> paquete (Formato B)."""
    LoteFormatoA.model_validate(lote)  # validar la entrada antes de procesar
    app = construir_grafo()
    resultado = app.invoke({"lote": lote, "procesados": [], "plan": [], "activos": [], "paquete": {}})
    return resultado["paquete"]


if __name__ == "__main__":
    # Consolas de Windows usan cp1252 por defecto y rompen con emojis/acentos
    sys.stdout.reconfigure(encoding="utf-8")

    if len(sys.argv) < 2:
        print("Uso: python -m orquestacion.pipeline <archivo_lote_formato_a.json>")
        sys.exit(1)

    lote = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    paquete = procesar_lote(lote)

    r = paquete["resumen_comunidad"]
    print(f"✅ Paquete {paquete['paquete_id']} generado y validado")
    print(f"   Procesados: {r['total_interacciones_procesadas']} mensajes")
    print(f"   Sentimiento: {r['sentimiento_predominante']} {r['distribucion_sentimiento']}")
    print(f"   Oportunidades: {r['oportunidades_detectadas']}  →  Activos: {len(paquete['activos'])}")
    for a in paquete["activos"]:
        print(f"     {a['activo_id']:<10} {a['formato']:<22} ← {a['lineage']['message_id']}")
    print()
    print(json.dumps(paquete, ensure_ascii=False, indent=2, default=str))
