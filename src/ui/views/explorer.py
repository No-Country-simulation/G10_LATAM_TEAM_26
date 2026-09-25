"""
CommunityLab AI - Vista: Detección & Scoring
Corre el motor sobre el lote y muestra la clasificación de cada mensaje (Formato P).
"""
import time

import streamlit as st

from src import config
from src.adapters.ingestion.loaders import interacciones_desde_payload
from src.core.orchestrator import procesar_detalle
from src.domain.schemas import BatchInputPayload
from src.ui.components.cards import render_interaction_card, render_kpi_card


def _es_oportunidad(p: dict) -> bool:
    umbral = config.UMBRALES_POR_TIPO.get(p["opportunity"]["type"])
    return umbral is not None and p["opportunity"]["opportunity_score"] >= umbral


def render_explorer_view(dataset: BatchInputPayload | None):
    st.markdown('<div class="saas-title">Detección & Scoring de Oportunidades</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Análisis por lotes con el grafo multiagente (analista → detector → '
                'estratega) y umbral por tipo de oportunidad.</div>', unsafe_allow_html=True)

    if not dataset:
        st.warning("Cargue un origen de datos en la barra lateral para continuar.")
        return

    total_disponibles = len(dataset.interacciones)

    col1, col2, col3 = st.columns([2, 1, 1], gap="medium")
    with col1:
        st.info(f"⚡ **Motor por lotes:** {config.TAMANO_LOTE} mensajes por llamada, hasta "
                f"{config.MAX_CONCURRENCIA} llamadas en paralelo y respaldo automático entre proveedores.")
        simulado = st.toggle("Modo simulado (sin IA, no gasta cuota)", value=False)
    with col2:
        cantidad = st.number_input("Mensajes a procesar:", min_value=1, max_value=total_disponibles,
                                   value=total_disponibles, step=1)
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        iniciar = st.button(f"⚡ Analizar {cantidad} msgs", type="primary", use_container_width=True)

    if iniciar:
        interacciones, metadatos = interacciones_desde_payload(dataset, int(cantidad))
        with st.spinner(f"Procesando {cantidad} mensajes..."):
            inicio = time.perf_counter()
            detalle = procesar_detalle(interacciones, metadatos, simulado=simulado)
            segundos = time.perf_counter() - inicio
        st.session_state["paquete"] = detalle["paquete"]
        st.session_state["procesados"] = detalle["procesados"]
        st.session_state["avisos"] = detalle["avisos"]
        st.session_state["modo_simulado"] = simulado
        st.session_state["textos_lote"] = {m["message_id"]: m for m in interacciones}
        st.session_state.pop("oci_result", None)
        st.success(f"Lote de {cantidad} mensajes procesado en {segundos:.1f} s"
                   f"{' (modo simulado)' if simulado else ''}.")

    paquete = st.session_state.get("paquete")
    if not paquete:
        return

    avisos = st.session_state.get("avisos", {})
    pendientes = sum(len(v) for v in avisos.values())
    if pendientes:
        st.warning(f"⚠️ El paquete quedó **parcial**: {len(avisos.get('sin_analisis', []))} mensajes sin análisis, "
                   f"{len(avisos.get('sin_clasificacion', []))} sin clasificar y "
                   f"{len(avisos.get('piezas_pendientes', []))} piezas sin redactar. Revisa las cuotas de la IA.")

    resumen = paquete["resumen_comunidad"]
    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("Mensajes procesados", resumen["total_interacciones_procesadas"], paquete["periodo_referencia"])
    with k2: render_kpi_card("Oportunidades", resumen["oportunidades_detectadas"], "Superan el umbral de su tipo")
    with k3: render_kpi_card("Borradores generados", len(paquete["activos"]), "Listos para curaduría")
    with k4: render_kpi_card("Consultas operativas", resumen["consultas_operativas"], "Para el equipo del programa")

    if resumen["tendencias_detectadas"]:
        with st.expander("📈 Tendencias detectadas", expanded=False):
            for t in resumen["tendencias_detectadas"]:
                st.markdown(f"- **{t['tema']}** · {t['descripcion']}")

    st.markdown("<br>", unsafe_allow_html=True)
    filtro = st.radio("Filtrar vista:", ["Solo oportunidades", "Descartados", "Todos"], horizontal=True)
    procesados = st.session_state.get("procesados", [])
    if filtro == "Solo oportunidades":
        mostrados = [p for p in procesados if _es_oportunidad(p)]
    elif filtro == "Descartados":
        mostrados = [p for p in procesados if not _es_oportunidad(p)]
    else:
        mostrados = procesados

    textos = st.session_state.get("textos_lote", {})
    st.caption(f"Mostrando {len(mostrados)} de {len(procesados)} mensajes evaluados:")
    for p in mostrados:
        mid = p["tracking"]["message_id"]
        original = textos.get(mid, {})
        render_interaction_card(
            msg_id=mid,
            author=original.get("autor") or "Miembro",
            channel=p["tracking"]["channel"] or "sin canal",
            text=original.get("texto", ""),
            op_type=p["opportunity"]["type"],
            score=p["opportunity"]["opportunity_score"],
        )
        st.caption(f"🧠 {p['opportunity']['reason']}")
