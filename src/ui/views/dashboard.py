"""
CommunityLab AI - Vista: Overview & Salud de la Comunidad
Dashboard analítico en tiempo real conectado a Oracle Cloud Infrastructure (OCI).
"""
import streamlit as st
from src.ui.components.cards import render_kpi_card
from src.domain.schemas import BatchInputPayload
from src.adapters.db.repository import (
    get_existing_message_ids, 
    get_community_analytics_summary,
    SessionLocal
)
from src.adapters.db.models import CommunityMessage


def render_dashboard_view(dataset: BatchInputPayload | None):
    st.markdown('<div class="saas-title">Overview & Salud de la Comunidad</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Diagnóstico continuo, clasificación de oportunidades y estado de distribución en OCI.</div>', unsafe_allow_html=True)

    if not dataset:
        st.warning("Seleccione una fuente de datos en la barra lateral para comenzar.")
        return

    # 1. CONSULTA DE ESTADO EN VIVO CONTRA ORACLE CLOUD
    analytics = get_community_analytics_summary()
    total_fuente = len(dataset.interacciones)
    total_oci = analytics["total_oci"]
    pendientes = max(0, total_fuente - total_oci)
    con_post = analytics["con_post"]
    sin_post = analytics["sin_post"]

    # 2. TARJETAS KPI DE IMPACTO
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card("Total en Fuente", total_fuente, "Discord / Lote activo")
    with k2:
        render_kpi_card("Procesados en OCI", total_oci, f"{int((total_oci/total_fuente)*100) if total_fuente else 0}% del total")
    with k3:
        render_kpi_card("Con Activo de Post", con_post, "Aprobados para distribución")
    with k4:
        render_kpi_card("Pendientes Análisis", pendientes, "Por procesar con IA")

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. BARRA DE PROGRESO DE COBERTURA
    if total_fuente > 0:
        ratio_procesado = min(1.0, total_oci / total_fuente)
        st.markdown(f"**Progreso de Ingesta y Análisis Comunitario:** `{int(ratio_procesado * 100)}% Completado`")
        st.progress(ratio_procesado)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. GRÁFICOS ANALÍTICOS DE CLASIFICACIÓN
    st.markdown("### 📊 Inteligencia y Clasificación Semántica (OCI)")
    
    col_chart1, col_chart2 = st.columns(2, gap="large")

    with col_chart1:
        with st.container(border=True):
            st.markdown("##### 🎯 Clasificación de Oportunidades")
            tipos_data = analytics.get("tipos", {})
            if tipos_data:
                # Renombrar para visualización amigable
                nombres_amigables = {
                    "SUCCESS_STORY": "Casos de Éxito",
                    "FAQ": "Preguntas / Tips",
                    "FEEDBACK": "Feedback Cursos",
                    "MILESTONE": "Hitos / Logros",
                    "NONE": "Casual / Descarte"
                }
                chart_dict = {nombres_amigables.get(k, k): v for k, v in tipos_data.items()}
                st.bar_chart(chart_dict, use_container_width=True, color="#4F46E5")
                st.caption("Distribución generada por Gemini tras evaluar el Opportunity Score.")
            else:
                st.info("Aún no hay mensajes analizados para graficar.")

    with col_chart2:
        with st.container(border=True):
            st.markdown("##### 💬 Tracción por Canal de Discord")
            canales_data = analytics.get("canales", {})
            if canales_data:
                st.bar_chart(canales_data, use_container_width=True, color="#059669")
                st.caption("Volumen de interacciones por canal temático de la comunidad.")
            else:
                st.info("Sin datos de canales disponibles.")

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. EMBUDO DE TRANSFORMACIÓN (POSTS vs SIN POST)
    st.markdown("### 🔄 Estado de Creación de Contenido")
    c_funnel1, c_funnel2 = st.columns([1, 2], gap="large")
    
    with c_funnel1:
        with st.container(border=True):
            st.markdown("##### 📌 Tasa de Transformación")
            if total_oci > 0:
                tasa = round((con_post / total_oci) * 100, 1)
                st.metric("Ratio de Conversión a Post", f"{tasa}%")
                st.write(f"- ✅ **Con Post Aprobado:** `{con_post}`")
                st.write(f"- ⏳ **Sin Post / En espera:** `{sin_post}`")
            else:
                st.info("Procesa un lote en 'Detección & Scoring' para ver el embudo.")

    with c_funnel2:
        with st.container(border=True):
            st.markdown("##### ⚡ Sentimiento de la Comunidad")
            sent_data = analytics.get("sentimientos", {})
            if sent_data:
                st.bar_chart(sent_data, use_container_width=True, color="#F59E0B")
            else:
                st.info("Sin métricas de sentimiento registradas.")

    st.markdown("<br>", unsafe_allow_html=True)

    # 6. FEED DINÁMICO CON ESTADO DE PROCESAMIENTO
    st.markdown("### 📥 Feed de Conversaciones & Trazabilidad")
    
    filtro_feed = st.radio(
        "Filtrar feed:", 
        ["Todos los Mensajes", "Solo con Post Generado", "Pendientes de Análisis"], 
        horizontal=True
    )

    # Consultar mensajes en BD para saber cuáles tienen post
    db_items = {}
    try:
        with SessionLocal() as db:
            msgs_db = db.query(CommunityMessage).all()
            for m in msgs_db:
                db_items[m.message_id] = {
                    "score": m.opportunity_score,
                    "tipo": m.opportunity_type,
                    "tiene_post": len(m.assets) > 0
                }
    except Exception:
        pass

    mensajes_mostrados = []
    for msg in dataset.interacciones:
        info_bd = db_items.get(msg.message_id)
        tiene_post = info_bd["tiene_post"] if info_bd else False
        procesado = info_bd is not None

        if filtro_feed == "Solo con Post Generado" and not tiene_post:
            continue
        if filtro_feed == "Pendientes de Análisis" and procesado:
            continue
        
        mensajes_mostrados.append((msg, info_bd, tiene_post, procesado))

    st.caption(f"Mostrando {len(mensajes_mostrados[:10])} de {len(mensajes_mostrados)} interacciones:")

    for msg, info_bd, tiene_post, procesado in mensajes_mostrados[:10]:
        with st.container(border=True):
            col_h1, col_h2 = st.columns([3, 1.2])
            with col_h1:
                st.markdown(f"**{msg.autor}** &nbsp; <code style='font-size:0.75rem;'>#{msg.channel}</code>", unsafe_allow_html=True)
            with col_h2:
                if tiene_post:
                    st.markdown("<div style='text-align:right;'><span style='background:#ECFDF5; color:#047857; font-weight:700; font-size:0.75rem; padding:0.2rem 0.5rem; border-radius:6px; border:1px solid #A7F3D0;'>✅ CON POST OCI</span></div>", unsafe_allow_html=True)
                elif procesado:
                    st.markdown(f"<div style='text-align:right;'><span style='background:#F1F5F9; color:#475569; font-weight:700; font-size:0.75rem; padding:0.2rem 0.5rem; border-radius:6px;'>PROCESADO ({info_bd['tipo']})</span></div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div style='text-align:right;'><span style='background:#FFFBEB; color:#B45309; font-weight:700; font-size:0.75rem; padding:0.2rem 0.5rem; border-radius:6px; border:1px solid #FDE68A;'>⏳ PENDIENTE</span></div>", unsafe_allow_html=True)

            st.markdown(f"<p style='color:#334155; font-size:0.92rem; line-height:1.5; margin:0.4rem 0;'>{msg.texto}</p>", unsafe_allow_html=True)
            
            score_txt = f" • Score OCI: **{info_bd['score']:.2f}**" if info_bd and info_bd['score'] else ""
            st.caption(f"ID: `{msg.message_id}`{score_txt}")