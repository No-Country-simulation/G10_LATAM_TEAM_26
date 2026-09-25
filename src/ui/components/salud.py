"""
CommunityLab AI - Salud de la comunidad
Sentimiento del lote, temas principales y mensajes que necesitan apoyo, a partir del paquete (sin llamadas a la IA).
"""
import html
from typing import Any, Dict, List, Tuple

import streamlit as st

SENTIMIENTOS = {
    "positive": ("😊", "Positivo", "pill-pos"),
    "neutral": ("😐", "Neutral", "pill-neu"),
    "negative": ("😟", "Negativo", "pill-neg"),
}


def estado_general(distribucion: Dict[str, int]) -> Tuple[str, str]:
    """Traduce la distribución del lote a una lectura para el equipo: (emoji, etiqueta).
    El paquete guarda positive/neutral/negative (spec); la etiqueta es solo de presentación."""
    total = sum(distribucion.values())
    if not total:
        return "—", "Sin datos"
    pos, neg, neu = (distribucion.get(s, 0) / total for s in ("positive", "negative", "neutral"))
    if neg >= 0.3:
        return "😟", "Con dificultades"
    if pos > 0.7:
        return "🤩", "Altamente positivo"
    if pos >= 0.4 and pos > neg:
        return "😊", "Mayormente positivo"
    if neu >= 0.6:
        return "😐", "Mayormente neutral"
    return "🤔", "Mixto"


def necesita_apoyo(p: Dict[str, Any]) -> bool:
    """Mensaje con sentimiento negativo o feedback sobre el programa."""
    return p["analysis"]["sentiment"] == "negative" or p["opportunity"]["type"] == "FEEDBACK"


def pill_sentimiento(sentimiento: str) -> str:
    emoji, etiqueta, clase = SENTIMIENTOS.get(sentimiento, SENTIMIENTOS["neutral"])
    return f"<span class='pill {clase}'>{emoji} {etiqueta}</span>"


def render_salud_comunidad(resumen: Dict[str, Any], procesados: List[Dict[str, Any]]):
    """Bloque de salud: estado general, barra de sentimiento, temas principales y alerta de apoyo."""
    distribucion = resumen["distribucion_sentimiento"]
    total = sum(distribucion.values()) or 1
    emoji, etiqueta = estado_general(distribucion)
    apoyo = sum(1 for p in procesados if necesita_apoyo(p))

    segmentos = "".join(
        f"<div class='salud-seg salud-{s}' style='width:{distribucion.get(s, 0) / total * 100:.1f}%'></div>"
        for s in ("positive", "neutral", "negative") if distribucion.get(s, 0))
    leyenda = " · ".join(
        f"{SENTIMIENTOS[s][0]} {distribucion.get(s, 0)} {SENTIMIENTOS[s][1].lower()}{'s' if distribucion.get(s, 0) != 1 else ''}"
        for s in ("positive", "neutral", "negative"))
    temas = "".join(f"<span class='pill pill-neutral'>{html.escape(t)}</span> "
                    for t in resumen.get("temas_principales", []))

    with st.container(border=True):
        c1, c2 = st.columns([1, 2], gap="large")
        with c1:
            st.markdown(f"<div class='kpi-label'>Salud de la comunidad</div>"
                        f"<div class='salud-estado'>{emoji} {etiqueta}</div>"
                        f"<div class='salud-leyenda'>{leyenda}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='kpi-label'>Distribución del sentimiento</div>"
                        f"<div class='salud-barra'>{segmentos}</div>"
                        f"<div class='kpi-label' style='margin-top:0.9rem'>Temas principales</div>"
                        f"<div style='margin-top:0.35rem'>{temas or '—'}</div>", unsafe_allow_html=True)
        if apoyo:
            st.warning(f"🆘 **{apoyo} {'mensaje necesita' if apoyo == 1 else 'mensajes necesitan'} apoyo** "
                       f"(sentimiento negativo o feedback). Revísalos con el filtro «Necesitan apoyo».")
