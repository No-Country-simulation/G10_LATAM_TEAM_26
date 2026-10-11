"""
Reglas de decisión del pipeline (el nodo "enrutar").

Esto es código determinístico A PROPÓSITO — no usa IA. El mismo mensaje
con el mismo score produce SIEMPRE la misma decisión, lo que hace el
sistema auditable y fácil de debuggear. La IA opina (score); las reglas
deciden (qué se genera).

Umbrales según spec.md:
    score >= 0.90        -> multicanal: post LinkedIn + destaque newsletter
    0.70 <= score < 0.90 -> UN activo, según el tipo de oportunidad
    score < 0.70         -> nada (solo cuenta para las métricas)
"""

UMBRAL_MULTICANAL = 0.90
UMBRAL_MINIMO = 0.70

# Qué formato de activo corresponde a cada tipo de oportunidad
# cuando el score está en la franja media (un solo activo).
FORMATO_POR_TIPO = {
    "SUCCESS_STORY": "post_linkedin",
    "FAQ": "sugerencia_faq",
    "TREND": "sugerencia_faq",          # una tendencia de dudas -> guía consolidada
    "MILESTONE": "destaque_newsletter",  # hitos de comunidad -> newsletter
    "FEEDBACK": "destaque_newsletter",   # cita destacada de feedback -> newsletter
}


def decidir_formatos(tipo: str, score: float) -> list[str]:
    """Devuelve la lista de formatos de activo a generar para una oportunidad.

    Lista vacía = no se genera nada (baja relevancia o tipo NONE).
    """
    if tipo == "NONE" or score < UMBRAL_MINIMO:
        return []
    if score >= UMBRAL_MULTICANAL:
        return ["post_linkedin", "destaque_newsletter"]
    formato = FORMATO_POR_TIPO.get(tipo)
    return [formato] if formato else []
