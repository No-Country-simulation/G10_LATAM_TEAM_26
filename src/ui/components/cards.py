"""
CommunityLab AI - Production UI Components
"""
import html

import streamlit as st

from src.ui.components.salud import pill_sentimiento


def render_kpi_card(label: str, value: str | int, subtext: str = ""):
    """Renderiza tarjeta métrica usando HTML limpio en una sola línea."""
    sub_html = f'<div class="kpi-trend">● {subtext}</div>' if subtext else ''
    card_html = f'<div class="kpi-container"><div class="kpi-label">{label}</div><div class="kpi-number">{value}</div>{sub_html}</div>'
    st.markdown(card_html, unsafe_allow_html=True)


def get_pill_class(op_type: str) -> str:
    mapping = {
        "SUCCESS_STORY": "pill-success",
        "TESTIMONIO": "pill-success",
        "FAQ": "pill-faq",
        "PREGUNTA_TECNICA": "pill-faq",
        "MILESTONE": "pill-milestone",
        "FEEDBACK": "pill-feedback",
    }
    return mapping.get(op_type.upper(), "pill-neutral")


def render_interaction_card(msg_id: str, author: str, channel: str, text: str, op_type: str = "CONVERSACION",
                            score: float = None, sentiment: str = None):
    """
    Usa el contenedor con borde nativo de Streamlit:
    Garantiza estabilidad total, sin bugs de parseo y con diseño limpio.
    """
    pill_cls = get_pill_class(op_type)
    sentiment_html = f"{pill_sentimiento(sentiment)} " if sentiment else ""

    with st.container(border=True):
        col_header_1, col_header_2 = st.columns([3, 1])
        with col_header_1:
            st.markdown(
                f"**{html.escape(author)}** &nbsp; <code style='font-size:0.75rem; color:#475569;'>#{html.escape(channel)}</code>",
                unsafe_allow_html=True
            )
        with col_header_2:
            score_text = f"&nbsp; <strong>Score: {score:.2f}</strong>" if score is not None else ""
            st.markdown(
                f"<div style='text-align: right;'>{sentiment_html}<span class='pill {pill_cls}'>{op_type}</span>{score_text}</div>",
                unsafe_allow_html=True
            )

        st.markdown(f"<p style='color: #334155; font-size: 0.92rem; line-height: 1.5; margin: 0.4rem 0;'>{html.escape(text)}</p>", unsafe_allow_html=True)
        st.caption(f"Trace ID: {msg_id}")