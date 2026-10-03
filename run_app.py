"""
CommunityLab AI - Router Principal
Coordina autenticación contra OCI, inicialización de tablas y enrutamiento hacia vistas.
"""
import os
import streamlit as st
from dotenv import load_dotenv

from src.ui.styles import apply_enterprise_theme
from src.adapters.ingestion.loaders import load_fixture_data, load_discord_raw_stream
from src.adapters.db.repository import init_db, verify_user, register_user
from src.ui.views.dashboard import render_dashboard_view
from src.ui.views.explorer import render_explorer_view
from src.ui.views.studio import render_studio_view
from src.ui.views.oci_view import render_oci_view

load_dotenv()

st.set_page_config(
    page_title="CommunityLab AI — Enterprise Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_enterprise_theme()

# 1. INICIALIZAR BASE DE DATOS (Crea las tablas en Oracle Cloud si no existen)
try:
    init_db()
except Exception as e:
    st.error(f"⚠️ Alerta de Base de Datos: {e}")


def check_auth() -> bool:
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
                # Autenticación segura consultando OCI / BD con hash bcrypt
                user = verify_user(username, password)
                if user:
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = user.username
                    st.session_state["role"] = user.role
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
    return False


def main():
    if not check_auth():
        st.stop()

    if "current_nav" not in st.session_state:
        st.session_state["current_nav"] = "overview"
    if "processed_results" not in st.session_state:
        st.session_state["processed_results"] = []
    if "approved_posts" not in st.session_state:
        st.session_state["approved_posts"] = {}

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

        user_role = st.session_state.get("role", "CURATOR")
        with st.container(border=True):
            st.markdown(f"**Operador:** `{st.session_state.get('username')}` ({user_role})")
            st.markdown("**Cloud:** `OCI Always Free`")

        st.markdown("<br>", unsafe_allow_html=True)
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
        st.caption("MÓDULOS DEL MOTOR")

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

        if st.button("☁️  Persistencia & OCI", use_container_width=True,
                     type="primary" if st.session_state["current_nav"] == "oci" else "secondary"):
            st.session_state["current_nav"] = "oci"
            st.rerun()

        # Gestión de Usuarios para ADMIN
        if user_role == "ADMIN":
            with st.expander("👤 Gestión de Usuarios (OCI)"):
                new_u = st.text_input("Nuevo Usuario", key="reg_u")
                new_p = st.text_input("Nueva Contraseña", type="password", key="reg_p")
                new_r = st.selectbox("Rol", ["CURATOR", "VIEWER", "ADMIN"], key="reg_r")
                if st.button("Crear Usuario", use_container_width=True):
                    if new_u and new_p:
                        created = register_user(new_u, new_p, role=new_r)
                        if created:
                            st.success(f"Usuario {new_u} registrado en OCI.")
                    else:
                        st.warning("Complete todos los campos.")

        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

    nav = st.session_state["current_nav"]
    dataset = st.session_state.get("dataset")

    if nav == "overview":
        render_dashboard_view(dataset)
    elif nav == "scoring":
        render_explorer_view(dataset)
    elif nav == "studio":
        render_studio_view()
    elif nav == "oci":
        render_oci_view(dataset)


if __name__ == "__main__":
    main()