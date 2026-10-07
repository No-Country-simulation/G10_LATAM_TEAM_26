"""
CommunityLab AI - Vista: Detección & Scoring (con Deduplicación en Oracle Cloud)
"""
import streamlit as st
from src.ui.components.cards import render_interaction_card
from src.domain.schemas import BatchInputPayload
from src.core.orchestrator import process_batch_pipeline
from src.adapters.db.repository import get_existing_message_ids


def render_explorer_view(dataset: BatchInputPayload | None):
    st.markdown('<div class="saas-title">Detección & Scoring de Oportunidades</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Análisis semántico consolidado en tiempo real con Inteligencia Artificial.</div>', unsafe_allow_html=True)

    if not dataset or not dataset.interacciones:
        st.warning("Cargue o seleccione un origen de datos en la barra lateral para continuar.")
        return

    # 1. Identificar la fuente activa de forma canónica
    source_activo = dataset.interacciones[0].source if dataset.interacciones else "discord"

    # 2. Consultar a Oracle Cloud ÚNICAMENTE los mensajes que pertenecen a esta fuente
    procesados_en_oci = get_existing_message_ids(source=source_activo)

    # 3. Función de comparación robusta (compara ID exacto o terminación numérica para evitar desajustes)
    def ya_fue_procesado(msg_id: str) -> bool:
        if not procesados_en_oci:
            return False
        if msg_id in procesados_en_oci:
            return True
        num_clean = msg_id.replace("DISC-", "").replace("MSG-", "")
        for p in procesados_en_oci:
            p_clean = p.replace("DISC-", "").replace("MSG-", "")
            if num_clean == p_clean or num_clean.endswith(p_clean) or p_clean.endswith(num_clean):
                return True
        return False

    # 4. Filtrar los mensajes verdaderamente pendientes de ESTA fuente
    mensajes_pendientes = [m for m in dataset.interacciones if not ya_fue_procesado(m.message_id)]
    
    total_disponibles = len(dataset.interacciones)
    total_guardados_fuente = len(dataset.interacciones) - len(mensajes_pendientes)
    total_pendientes = len(mensajes_pendientes)

    # Si todos los mensajes ya están registrados
    if total_pendientes < 0:
        total_pendientes = 0

    # 5. Métricas visuales 100% aisladas
    m1, m2, m3 = st.columns(3)
    with m1: 
        st.metric("Total en Fuente Activa", total_disponibles)
    with m2: 
        st.metric(f"Guardados en OCI", total_guardados_fuente)
    with m3: 
        st.metric("Pendientes por Analizar", total_pendientes)

    st.markdown("<br>", unsafe_allow_html=True)

    # 6. Control de Lote: Completado vs Pendiente
    if total_pendientes == 0:
        st.success(f"🎉 ¡Todos los mensajes de esta fuente ({source_activo}) ya han sido analizados y guardados en Oracle Cloud!")
        st.info("Pasa al módulo **'Content Studio'** para curar los activos o selecciona otro origen de datos en el menú lateral.")
    else:
        col1, col2, col3 = st.columns([2, 1, 1], gap="medium")
        with col1:
            st.info(f"💡 Hay **{total_pendientes} mensajes nuevos** de esta fuente esperando análisis de IA.")
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
            with st.spinner(f"Enviando lote de {cantidad} mensajes a la IA..."):
                lote_a_procesar = mensajes_pendientes[:cantidad]
                results, resumen = process_batch_pipeline(lote_a_procesar)

                if "results_dict" not in st.session_state:
                    st.session_state["results_dict"] = {}

                for proc, assets in results:
                    st.session_state["results_dict"][proc.message_id] = (proc, assets)

                st.session_state["processed_results"] = list(st.session_state["results_dict"].values())
                st.session_state["resumen_comunidad"] = resumen

            st.success(f"¡Lote de {cantidad} mensajes procesado y guardado en Oracle Cloud!")
            st.rerun()

    # Visualización garantizada de resultados evaluados en la sesión
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

        st.caption(f"Mostrando {len(items_a_mostrar)} de {len(resultados)} interacciones evaluadas:")
        
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