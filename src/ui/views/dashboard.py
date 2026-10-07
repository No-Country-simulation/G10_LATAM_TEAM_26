"""
CommunityLab AI - Vista: Overview & Métricas
"""
import streamlit as st
from src.ui.components.cards import render_kpi_card, render_interaction_card
from src.domain.schemas import BatchInputPayload
from src.adapters.db import repository
from src.ui.components.salud import render_salud_comunidad


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
    paquete = st.session_state.get("paquete")
    if paquete:
        render_salud_comunidad(paquete["resumen_comunidad"], st.session_state.get("procesados", []))
    else:
        st.info("📊 La salud y el sentimiento de la comunidad aparecen aquí después de analizar el lote en "
                "**Detección & Scoring**.")

    render_historico()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Feed de Conversaciones Recientes (Datos Normalizados)")

    for msg in dataset.interacciones[:6]:
        render_interaction_card(
            msg_id=msg.message_id,
            author=msg.autor,
            channel=msg.channel,
            text=msg.texto,
            op_type=msg.tipo_declarado or "otro"  # opcional en el Formato A; por defecto 'otro' (spec.md)
        )


def render_historico():
    """Todo lo procesado con IA y guardado en la base de la comunidad, a lo largo de todos los lotes."""
    try:
        historico = repository.resumen_historico()
    except Exception:
        return
    if not historico["mensajes"]:
        return
    with st.expander(f"🗃️ Histórico en la base ({repository.nombre_motor()}): {historico['mensajes']} mensajes", expanded=False):
        oportunidades = sum(historico["tipos"].get(t, 0) for t in ("SUCCESS_STORY", "MILESTONE", "FAQ"))
        c1, c2, c3 = st.columns(3)
        with c1: render_kpi_card("Mensajes procesados", historico["mensajes"], "Todos los lotes")
        with c2: render_kpi_card("Con valor de contenido", oportunidades, "Éxitos, logros y FAQ")
        with c3: render_kpi_card("Activos registrados", sum(historico["activos"].values()),
                                 f"{historico['activos'].get('aprobado', 0)} aprobados")
        c4, c5, c6 = st.columns(3)
        c4.caption("Por tipo"); c4.json(historico["tipos"], expanded=False)
        c5.caption("Por sentimiento"); c5.json(historico["sentimientos"], expanded=False)
        c6.caption("Canales más activos"); c6.json(historico["canales"], expanded=False)
