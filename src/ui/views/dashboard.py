"""
CommunityLab AI - Vista: Overview & Métricas
"""
import streamlit as st
from src.ui.components.cards import render_kpi_card, render_interaction_card
from src.domain.schemas import BatchInputPayload


def render_dashboard_view(dataset: BatchInputPayload | None):
    st.markdown('<div class="saas-title">Overview de la Comunidad</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Monitoreo y análisis de conversaciones orgánicas en tiempo real.</div>', unsafe_allow_html=True)

    if not dataset:
        st.warning("No hay datos cargados para mostrar métricas.")
        return

    total_msgs = len(dataset.interacciones)
    testimonios = sum(1 for m in dataset.interacciones if m.tipo_declarado == "testimonio")
    dudas = sum(1 for m in dataset.interacciones if m.tipo_declarado == "pregunta_tecnica")
    feedback = sum(1 for m in dataset.interacciones if m.tipo_declarado == "feedback")

    c1, c2, c3, c4 = st.columns(4)
    with c1: render_kpi_card("Total Interacciones", total_msgs, f"Período: {dataset.periodo_referencia}")
    with c2: render_kpi_card("Historias de Éxito", testimonios, "Candidatos a Success Story")
    with c3: render_kpi_card("Dudas Técnicas", dudas, "Contenido FAQ / Mentoría")
    with c4: render_kpi_card("Feedback Programas", feedback, "Oportunidades de Mejora")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Feed de Conversaciones Recientes (Datos Normalizados)")

    for msg in dataset.interacciones[:6]:
        render_interaction_card(
            msg_id=msg.message_id,
            author=msg.autor,
            channel=msg.channel,
            text=msg.texto,
            op_type=msg.tipo_declarado
        )