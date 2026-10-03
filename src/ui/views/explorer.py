"""
CommunityLab AI - Vista: Detección & Scoring (Sin Duplicados y con Ventana Deslizante)
"""
import streamlit as st
from src.ui.components.cards import render_interaction_card
from src.domain.schemas import BatchInputPayload
from src.core.orchestrator import process_batch_pipeline
from src.adapters.db.repository import get_existing_message_ids


def render_explorer_view(dataset: BatchInputPayload | None):
    st.markdown('<div class="saas-title">Detección & Scoring de Oportunidades</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Análisis semántico consolidado en tiempo real con Inteligencia Artificial.</div>', unsafe_allow_html=True)

    if not dataset:
        st.warning("Cargue un origen de datos en la barra lateral para continuar.")
        return

    # 1. Consultar a Oracle Cloud qué mensajes ya existen
    procesados_en_oci = get_existing_message_ids()
    
    # 2. Filtrar únicamente los pendientes de analizar
    mensajes_pendientes = [m for m in dataset.interacciones if m.message_id not in procesados_en_oci]
    
    total_disponibles = len(dataset.interacciones)
    total_pendientes = len(mensajes_pendientes)
    total_en_bd = len(procesados_en_oci)

    # Métricas en vivo
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Total en Fuente", total_disponibles)
    with m2:
        st.metric("Guardados en Oracle Cloud (OCI)", total_en_bd)
    with m3:
        st.metric("Pendientes por Analizar", total_pendientes)

    st.markdown("<br>", unsafe_allow_html=True)

    if total_pendientes == 0:
        st.success("🎉 ¡Todos los mensajes de este origen de datos ya han sido analizados y guardados en OCI!")
        st.info("Pasa al módulo **'Content Studio'** para curar los activos de marketing.")
    else:
        col1, col2, col3 = st.columns([2, 1, 1], gap="medium")
        with col1:
            st.info(f"💡 Hay **{total_pendientes} mensajes nuevos** esperando análisis.")
        with col2:
            cantidad = st.number_input(
                "Lote a procesar:", 
                min_value=1, 
                max_value=total_pendientes, 
                value=min(10, total_pendientes), 
                step=1
            )
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            iniciar = st.button(f"⚡ Analizar siguientes {cantidad}", type="primary", use_container_width=True)

        if iniciar:
            with st.spinner(f"Enviando lote de {cantidad} mensajes nuevos a la IA..."):
                lote_a_procesar = mensajes_pendientes[:cantidad]
                results, resumen = process_batch_pipeline(lote_a_procesar)

                # DEDUPLICACIÓN VISUAL: Usamos un dict por message_id para evitar duplicados en memoria
                if "results_dict" not in st.session_state:
                    st.session_state["results_dict"] = {}

                for proc, assets in results:
                    st.session_state["results_dict"][proc.message_id] = (proc, assets)

                # Mantener lista ordenada
                st.session_state["processed_results"] = list(st.session_state["results_dict"].values())
                st.session_state["resumen_comunidad"] = resumen

            st.success(f"¡Lote de {cantidad} mensajes procesado y guardado en Oracle Cloud!")
            st.rerun()

    # RENDERIZADO GARANTIZADO SIN REPETIDOS
    resultados = st.session_state.get("processed_results", [])
    if resultados:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Mensajes Evaluados en la Sesión")
        
        filtro = st.radio(
            "Filtrar vista:", 
            ["Todos", "Solo Oportunidades (Score ≥ 0.70)", "Descartados (< 0.70)"], 
            horizontal=True
        )

        items_a_mostrar = []
        for proc, assets in resultados:
            score = float(proc.opportunity.opportunity_score)
            if filtro == "Solo Oportunidades (Score ≥ 0.70)" and score >= 0.70:
                items_a_mostrar.append((proc, assets))
            elif filtro == "Descartados (< 0.70)" and score < 0.70:
                items_a_mostrar.append((proc, assets))
            elif filtro == "Todos":
                items_a_mostrar.append((proc, assets))

        st.caption(f"Mostrando {len(items_a_mostrar)} de {len(resultados)} interacciones únicas:")
        
        for proc, assets in items_a_mostrar:
            op_tipo = proc.opportunity.type
            op_tipo_str = op_tipo.value if hasattr(op_tipo, "value") else str(op_tipo)
            
            render_interaction_card(
                msg_id=proc.message_id,
                author=proc.autor_anonimizado,
                channel=proc.channel,
                text=proc.texto_limpio,
                op_type=op_tipo_str,
                score=float(proc.opportunity.opportunity_score)
            )