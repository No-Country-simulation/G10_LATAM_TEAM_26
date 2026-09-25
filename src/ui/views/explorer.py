"""
CommunityLab AI - Vista: Detección & Scoring (Micro-Batching Instantáneo)
"""
import streamlit as st
from src.ui.components.cards import render_interaction_card
from src.domain.schemas import BatchInputPayload
from src.core.orchestrator import process_batch_pipeline


def render_explorer_view(dataset: BatchInputPayload | None):
    st.markdown('<div class="saas-title">Detección & Scoring de Oportunidades</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Análisis semántico consolidado en tiempo real con Inteligencia Artificial.</div>', unsafe_allow_html=True)

    if not dataset:
        st.warning("Cargue un origen de datos en la barra lateral para continuar.")
        return

    total_disponibles = len(dataset.interacciones)

    col1, col2, col3 = st.columns([2, 1, 1], gap="medium")
    with col1:
        st.info("⚡ **Arquitectura Batch:** Analiza hasta 30 mensajes en **1 sola llamada a la IA**, sin esperas ni riesgo de saturación de cuota.")
    with col2:
        cantidad = st.number_input(
            "Mensajes a procesar:", 
            min_value=5, 
            max_value=total_disponibles, 
            value=min(25, total_disponibles), 
            step=5
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        iniciar = st.button(f"⚡ Analizar {cantidad} msgs", type="primary", use_container_width=True)

    if iniciar:
        with st.spinner(f"Enviando lote de {cantidad} mensajes a la IA..."):
            mensajes_a_procesar = dataset.interacciones[:cantidad]
            results, resumen = process_batch_pipeline(mensajes_a_procesar)
            st.session_state["processed_results"] = results
            st.session_state["resumen_comunidad"] = resumen

        st.success(f"¡Lote de {cantidad} mensajes procesado en una sola llamada!")

if st.session_state.get("processed_results"):
        st.markdown("<br>", unsafe_allow_html=True)
        
        filtro = st.radio(
            "Filtrar vista:", 
            ["Todos", "Solo Oportunidades (Score ≥ 0.70)", "Descartados (< 0.70)"], 
            horizontal=True
        )
        
        todos_los_items = st.session_state["processed_results"]
        
        if filtro == "Solo Oportunidades (Score ≥ 0.70)":
            items_mostrados = [x for x in todos_los_items if x[0].opportunity.opportunity_score >= 0.70]
        elif filtro == "Descartados (< 0.70)":
            items_mostrados = [x for x in todos_los_items if x[0].opportunity.opportunity_score < 0.70]
        else:
            items_mostrados = todos_los_items

        st.caption(f"Mostrando {len(items_mostrados)} de {len(todos_los_items)} interacciones evaluadas:")
        for proc, assets in items_mostrados:
            render_interaction_card(
                msg_id=proc.message_id,
                author=proc.autor_anonimizado,
                channel=proc.channel,
                text=proc.texto_limpio,
                op_type=proc.opportunity.type.value,
                score=proc.opportunity.opportunity_score
            )