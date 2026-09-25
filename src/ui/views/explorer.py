"""
CommunityLab AI - Vista: Detección & Scoring
Corre el motor sobre el lote y muestra la clasificación de cada mensaje (Formato P).
"""
import time

import streamlit as st

from src import config
from src.adapters.ingestion.loaders import interacciones_desde_payload
from src.core.orchestrator import clasificar_en_segundo_plano, generar_contenido
from src.domain.schemas import BatchInputPayload
from src.ui.components.cards import render_interaction_card, render_kpi_card
from src.ui.components.salud import necesita_apoyo, render_salud_comunidad


def _es_oportunidad(p: dict) -> bool:
    umbral = config.UMBRALES_POR_TIPO.get(p["opportunity"]["type"])
    return umbral is not None and p["opportunity"]["opportunity_score"] >= umbral


def _tarjeta(p: dict, textos: dict) -> None:
    mid = p["tracking"]["message_id"]
    original = textos.get(mid, {})
    render_interaction_card(
        msg_id=mid,
        author=original.get("autor") or "Miembro",
        channel=p["tracking"]["channel"] or "sin canal",
        text=original.get("texto", ""),
        op_type=p["opportunity"]["type"],
        score=p["opportunity"]["opportunity_score"],
        sentiment=p["analysis"]["sentiment"],
    )
    st.caption(f"🧠 {p['opportunity']['reason']}")


@st.fragment(run_every=1)
def progreso_clasificacion():
    """Se refresca cada segundo mientras la clasificación corre: muestra los mensajes lote por lote."""
    clasificacion = st.session_state.get("clasificacion")
    if not clasificacion or st.session_state.get("paquete"):
        return
    if not clasificacion.terminado:
        parciales = clasificacion.parciales
        textos = st.session_state.get("textos_lote", {})
        orden = {mid: i for i, mid in enumerate(textos)}
        st.progress(len(parciales) / max(clasificacion.total, 1),
                    text=f"🔎 Clasificando: {len(parciales)} de {clasificacion.total} mensajes "
                         f"({clasificacion.transcurrido:.0f} s). Los resultados aparecen a medida que llega cada lote.")
        for p in sorted(parciales, key=lambda p: orden.get(p["tracking"]["message_id"], 0)):
            _tarjeta(p, textos)
        return
    if clasificacion.error:
        st.session_state.pop("clasificacion", None)
        st.error(f"No se pudo clasificar el lote ({type(clasificacion.error).__name__}). Revisa las API keys y "
                 f"las cuotas de la IA, o prueba el modo simulado.")
        return
    detalle = clasificacion.detalle
    st.session_state["paquete"] = detalle["paquete"]
    st.session_state["procesados"] = detalle["procesados"]
    st.session_state["avisos"] = detalle["avisos"]
    st.session_state["segundos_clasificacion"] = clasificacion.segundos
    st.session_state["inicio_redaccion"] = time.perf_counter()
    st.session_state["generacion"] = generar_contenido(detalle, simulado=st.session_state.get("modo_simulado", False))
    st.rerun(scope="app")  # pasa a la vista completa con métricas, salud y filtros


@st.fragment(run_every=2)
def progreso_redaccion():
    """Se refresca solo mientras los borradores se redactan en segundo plano."""
    generacion = st.session_state.get("generacion")
    if not generacion:
        return
    listos, total = len(generacion.activos), generacion.total_piezas
    clasif = st.session_state.get("segundos_clasificacion", 0)
    if not generacion.terminado:
        st.progress(generacion.lotes_listos / max(len(generacion.lotes), 1),
                    text=f"✍️ Clasificación lista en {clasif:.1f} s. Redactando borradores en segundo plano: "
                         f"{listos} de {total} listos (ya puedes revisarlos en Content Studio).")
        return
    if not st.session_state.get("redaccion_notificada"):
        st.session_state["segundos_redaccion"] = time.perf_counter() - st.session_state["inicio_redaccion"]
        st.session_state["avisos"]["piezas_pendientes"] = list(generacion.pendientes)
        st.session_state["redaccion_notificada"] = True
        st.rerun(scope="app")  # actualiza métricas y avisos con el resultado final
    simulado = " (modo simulado)" if st.session_state.get("modo_simulado") else ""
    st.success(f"Clasificación en {clasif:.1f} s y {listos} de {total} borradores redactados en "
               f"{st.session_state.get('segundos_redaccion', 0):.1f} s más{simulado}.")


def render_explorer_view(dataset: BatchInputPayload | None):
    st.markdown('<div class="saas-title">Detección & Scoring de Oportunidades</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Análisis por lotes con el grafo multiagente (clasificación de sentimiento, '
                'temas y tipo → redacción en segundo plano) y umbral por tipo de oportunidad.</div>',
                unsafe_allow_html=True)

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
        for clave in ("paquete", "procesados", "avisos", "generacion", "redaccion_notificada", "oci_result"):
            st.session_state.pop(clave, None)
        st.session_state["modo_simulado"] = simulado
        st.session_state["textos_lote"] = {m["message_id"]: m for m in interacciones}
        st.session_state["clasificacion"] = clasificar_en_segundo_plano(interacciones, metadatos, simulado=simulado)

    progreso_clasificacion()
    paquete = st.session_state.get("paquete")
    if not paquete:
        return

    progreso_redaccion()
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
    feedback = resumen.get("feedback_recibido", 0)
    with k4: render_kpi_card("Para el equipo del programa", resumen["consultas_operativas"] + feedback,
                             f"{resumen['consultas_operativas']} consultas operativas · {feedback} feedback")

    procesados = st.session_state.get("procesados", [])
    render_salud_comunidad(resumen, procesados)

    if resumen["tendencias_detectadas"]:
        with st.expander("📈 Tendencias detectadas", expanded=False):
            for t in resumen["tendencias_detectadas"]:
                st.markdown(f"- **{t['tema']}** · {t['descripcion']}")

    st.markdown("<br>", unsafe_allow_html=True)
    filtro = st.radio("Filtrar vista:", ["Solo oportunidades", "Necesitan apoyo", "Feedback", "Descartados", "Todos"],
                      horizontal=True)
    if filtro == "Solo oportunidades":
        mostrados = [p for p in procesados if _es_oportunidad(p)]
    elif filtro == "Necesitan apoyo":
        mostrados = [p for p in procesados if necesita_apoyo(p)]
    elif filtro == "Feedback":
        mostrados = [p for p in procesados if p["opportunity"]["type"] == "FEEDBACK"]
    elif filtro == "Descartados":
        mostrados = [p for p in procesados if not _es_oportunidad(p)]
    else:
        mostrados = procesados

    textos = st.session_state.get("textos_lote", {})
    st.caption(f"Mostrando {len(mostrados)} de {len(procesados)} mensajes evaluados:")
    for p in mostrados:
        _tarjeta(p, textos)
