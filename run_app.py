"""
CommunityLab AI - Enterprise Platform Application
Pipeline Multiagente con Curaduría Human-in-the-Loop integrada
"""
import os
import json
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv


from src.ui.styles import apply_enterprise_theme
from src.ui.components.cards import render_kpi_card, render_interaction_card
from src.ui.components.post_editor import render_linkedin_editor
from src.domain.schemas import BatchInputPayload
from src.core.orchestrator import process_single_interaction
from src.adapters.ingestion.loaders import load_fixture_data, load_discord_raw_stream


load_dotenv()

st.set_page_config(
    page_title="CommunityLab AI — Enterprise Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 1. Aplicar estilos adaptables
apply_enterprise_theme()


def check_auth() -> bool:
    """Guard de autenticación."""
    if st.session_state.get("authenticated", False):
        return True

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("""
            <div style="text-align: center; margin-bottom: 1.5rem; margin-top: 0.5rem;">
                <div style="font-size: 2rem; font-weight: 800; color: #4F46E5;">⚡ CommunityLab AI</div>
                <p style="color: #64748B; font-size: 0.9rem; margin-top: 0.2rem;">Motor Inteligente de Transformación & Marketing</p>
            </div>
            """, unsafe_allow_html=True)

            username = st.text_input("Usuario Corporativo", placeholder="admin")
            password = st.text_input("Contraseña de Acceso", type="password", placeholder="••••••••")
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Iniciar Sesión", use_container_width=True, type="primary"):
                admin_user = os.getenv("ADMIN_USER", "admin")
                admin_pass = os.getenv("ADMIN_PASSWORD", "CommunityLab2026!")
                
                if username == admin_user and password == admin_pass:
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = username
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
    return False


def load_dataset() -> BatchInputPayload | None:
    fixture_path = Path("data/fixtures/lote_ejemplo_formato_a.json")
    if not fixture_path.exists():
        st.error(f"No se encontró el lote de datos en: {fixture_path}")
        return None
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return BatchInputPayload(**data)


def main():
    if not check_auth():
        st.stop()

    if "dataset" not in st.session_state:
        st.session_state["dataset"] = load_dataset()
    dataset = st.session_state["dataset"]

    # Inicializar memoria de sesión para el pipeline
    if "current_nav" not in st.session_state:
        st.session_state["current_nav"] = "overview"
    if "processed_results" not in st.session_state:
        st.session_state["processed_results"] = []
    if "approved_posts" not in st.session_state:
        st.session_state["approved_posts"] = {}

    # SIDEBAR
    with st.sidebar:
        st.markdown("""
        <div style="padding: 0.25rem 0 0.8rem 0;">
            <div style="font-size: 1.25rem; font-weight: 800; display: flex; align-items: center; gap: 0.4rem;">
                <span style="color: #4F46E5;">⚡</span> CommunityLab
            </div>
            <div style="font-size: 0.75rem; color: #64748B; font-weight: 600; margin-top: 0.1rem;">
                Oracle Next Education • Hackathon G10
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown(f"**Operador:** `{st.session_state.get('username')}`")
            st.markdown("**Cloud:** `OCI Always Free`")

        # SELECTOR DE ORIGEN DE DATOS
        st.caption("ORIGEN DE DATOS")
        data_source = st.selectbox(
            "Fuente activa:",
            ["Dataset Estándar (30 msgs)", "Discord Live (.jsonl)"],
            index=0,
            label_visibility="collapsed"
        )

        if data_source == "Dataset Estándar (30 msgs)":
            dataset = load_fixture_data()
        else:
            dataset = load_discord_raw_stream()
            if dataset is None:
                st.warning("No hay capturas en data/raw/. Usando dataset estándar como fallback.")
                dataset = load_fixture_data()

        st.session_state["dataset"] = dataset
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("MÓDULOS DEL SISTEMA")

        if st.button("📊  Overview & Métricas", use_container_width=True, 
                     type="primary" if st.session_state["current_nav"] == "overview" else "secondary"):
            st.session_state["current_nav"] = "overview"
            st.rerun()

        if st.button("🎯  Detección & Scoring", use_container_width=True,
                     type="primary" if st.session_state["current_nav"] == "scoring" else "secondary"):
            st.session_state["current_nav"] = "scoring"
            st.rerun()

        if st.button("✍️  Content Studio (Curaduría)", use_container_width=True,
                     type="primary" if st.session_state["current_nav"] == "studio" else "secondary"):
            st.session_state["current_nav"] = "studio"
            st.rerun()

        if st.button("☁️  Persistencia & Trazabilidad", use_container_width=True,
                     type="primary" if st.session_state["current_nav"] == "oci" else "secondary"):
            st.session_state["current_nav"] = "oci"
            st.rerun()

        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

    nav = st.session_state["current_nav"]

    # 1. OVERVIEW & MÉTRICAS
    if nav == "overview":
        st.markdown('<div class="saas-title">Overview de la Comunidad</div>', unsafe_allow_html=True)
        st.markdown('<div class="saas-subtitle">Monitoreo y análisis de conversaciones orgánicas en tiempo real.</div>', unsafe_allow_html=True)

        if dataset:
            total_msgs = len(dataset.interacciones)
            testimonios = sum(1 for m in dataset.interacciones if m.tipo_declarado == "testimonio")
            dudas = sum(1 for m in dataset.interacciones if m.tipo_declarado == "pregunta_tecnica")
            feedback = sum(1 for m in dataset.interacciones if m.tipo_declarado == "feedback")

            c1, c2, c3, c4 = st.columns(4)
            with c1: render_kpi_card("Total Interacciones", total_msgs, "Período: Semana 04")
            with c2: render_kpi_card("Historias de Éxito", testimonios, "Candidatos a Success Story")
            with c3: render_kpi_card("Dudas Técnicas", dudas, "Contenido FAQ / Mentoría")
            with c4: render_kpi_card("Feedback Cursos", feedback, "Oportunidad de Mejora")

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

    # 2. DETECCIÓN & SCORING
    elif nav == "scoring":
        st.markdown('<div class="saas-title">Detección & Scoring de Oportunidades</div>', unsafe_allow_html=True)
        st.markdown('<div class="saas-subtitle">Priorización algorítmica y filtrado con agentes de IA.</div>', unsafe_allow_html=True)

        col_left, col_right = st.columns([3, 1])
        with col_left:
            st.info("💡 **Regla de Negocio:** Interacciones con **Score ≥ 0.70** pasan automáticamente al *Content Studio* para redacción editorial.")
        with col_right:
            if st.button("⚡ Analizar Lote con IA", type="primary", use_container_width=True):
                with st.spinner("Ejecutando Agentes (Analyst + Detector)..."):
                    results = []
                    # Procesamos los primeros 8 mensajes representativos del lote
                    for msg in dataset.interacciones[:8]:
                        proc, assets = process_single_interaction(msg)
                        results.append((proc, assets))
                    st.session_state["processed_results"] = results
                st.success("¡Lote analizado con éxito!")

        if st.session_state["processed_results"]:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("#### Resultados del Análisis Multiagente")
            
            for proc, assets in st.session_state["processed_results"]:
                score = proc.opportunity.opportunity_score
                render_interaction_card(
                    msg_id=proc.message_id,
                    author=proc.autor_anonimizado,
                    channel=proc.channel,
                    text=proc.texto_limpio,
                    op_type=proc.opportunity.type.value,
                    score=score
                )
        else:
            st.caption("Presiona '⚡ Analizar Lote con IA' para iniciar el procesamiento.")

    # 3. CONTENT STUDIO (CURADURÍA HUMANA)
    elif nav == "studio":
        st.markdown('<div class="saas-title">Content Studio — Human-in-the-Loop</div>', unsafe_allow_html=True)
        st.markdown('<div class="saas-subtitle">Supervisión, ajuste editorial y aprobación previa a la persistencia.</div>', unsafe_allow_html=True)

        # Filtrar solo oportunidades con score >= 0.70 que generaron activos
        high_value = [item for item in st.session_state["processed_results"] if item[1] is not None]

        if not high_value:
            st.warning("No hay borradores disponibles. Ve a 'Detección & Scoring' y ejecuta el análisis primero.")
        else:
            st.success(f"Se detectaron **{len(high_value)}** oportunidades de alto impacto listas para curaduría.")
            
            # Selector de la oportunidad a curar
            options = [f"{p.message_id} | {p.autor_anonimizado} ({p.opportunity.type.value} - Score {p.opportunity.opportunity_score:.2f})" for p, a in high_value]
            selected_idx = st.selectbox("Selecciona una oportunidad para revisar:", range(len(options)), format_func=lambda x: options[x])
            
            proc, assets = high_value[selected_idx]
            
            if assets.post_linkedin:
                    post = assets.post_linkedin
                    approved, rejected, ed_title, ed_copy = render_linkedin_editor(
                        msg_id=proc.message_id,
                        author=proc.autor_anonimizado,
                        default_title=post.titulo,
                        default_copy=post.texto_copy
                    )

            if approved:
                    st.session_state["approved_posts"][proc.message_id] = {
                        "post_id": f"POST-{proc.message_id.replace('MSG-', '')}",
                        "title": ed_title,
                        "copy": ed_copy,
                        "author": proc.autor_anonimizado,
                        "origin_msg_id": proc.message_id,
                        "score": proc.opportunity.opportunity_score,
                        "status": "APPROVED_FOR_OCI"
                    }
                    st.toast(f"✅ Activo para {proc.message_id} aprobado!", icon="🎉")
                
            if rejected:
                    if proc.message_id in st.session_state["approved_posts"]:
                        del st.session_state["approved_posts"][proc.message_id]
                    st.toast(f"🚫 Activo {proc.message_id} descartado.", icon="⚠️")

    # 4. PERSISTENCIA & OCI
    elif nav == "oci":
        st.markdown('<div class="saas-title">Trazabilidad & Persistencia de Activos</div>', unsafe_allow_html=True)
        st.markdown('<div class="saas-subtitle">Registro de activos aprobados listos para sincronización en la nube.</div>', unsafe_allow_html=True)

        c1, c2 = st.columns([1.2, 1], gap="large")
        with c1:
            with st.container(border=True):
                st.markdown("##### 📍 Lineage y Activos Aprobados en Sesión")
                approved = st.session_state.get("approved_posts", {})
                if not approved:
                    st.info("Aún no has aprobado ningún post en el Content Studio.")
                else:
                    st.markdown(f"Total aprobados: **{len(approved)}**")
                    for k, item in approved.items():
                        st.code(f"""{item['post_id']} (LinkedIn)
 └──► {item['status']} (Score {item['score']:.2f})
       └──► {item['origin_msg_id']} ({item['author']})""", language="text")

        with c2:
            with st.container(border=True):
                st.markdown("##### ☁️ Destino OCI Object Storage (Always Free)")
                st.markdown("**Bucket:** `communitylab-bucket`")
                st.markdown("**Namespace:** `oracle-one-latam-g10`")
                st.caption("Ruta configurada: `generated/linkedin/2026-semana-04/`")
                st.info("ℹ️ La persistencia cloud está preparada. Se conectará con el SDK de OCI en la fase final.")


if __name__ == "__main__":
    main()