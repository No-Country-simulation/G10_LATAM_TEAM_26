"""
CommunityLab AI - Router Principal
Coordina autenticación (usuarios de la base de la comunidad), layout global y enrutamiento hacia las vistas.
"""
import os
import streamlit as st
from dotenv import load_dotenv

from src.ui.styles import apply_enterprise_theme
from src.adapters.db import repository
from src.adapters.ingestion.loaders import load_discord_raw_stream, load_fixture_data, load_uploaded_json_file
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


@st.cache_resource
def iniciar_base() -> str:
    """Crea las tablas (OCI Autonomous Database o SQLite local) una vez por proceso. Devuelve el error, si hubo."""
    try:
        repository.init_db()
        return ""
    except Exception as error:
        return f"{type(error).__name__}: {str(error)[:160]}"


def autenticar(usuario: str, clave: str):
    """(nombre, rol) si las credenciales son válidas: primero contra la base y, como respaldo si la base no responde
    o el usuario no existe ahí, contra ADMIN_USER / ADMIN_PASSWORD del .env."""
    registro = repository.verify_user(usuario, clave)
    if registro:
        return registro.username, registro.role
    admin_user, admin_pass = os.getenv("ADMIN_USER", "admin"), os.getenv("ADMIN_PASSWORD", "")
    if admin_pass and usuario == admin_user and clave == admin_pass:
        return usuario, "ADMIN"
    return None


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
                acceso = autenticar(username, password)
                if acceso:
                    st.session_state["authenticated"] = True
                    st.session_state["username"], st.session_state["role"] = acceso
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
    return False


def main():
    error_base = iniciar_base()
    if not check_auth():
        st.stop()
    rol = st.session_state.get("role", "CURATOR")

    if "current_nav" not in st.session_state:
        st.session_state["current_nav"] = "overview"

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
            st.markdown(f"**Operador:** `{st.session_state.get('username')}` ({rol})")
            st.markdown("**Cloud:** `OCI Always Free`")
            st.markdown(f"**Base:** `{repository.nombre_motor()}`")
            if error_base:
                st.caption(f"⚠️ La base no respondió: {error_base}")

        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("ORIGEN DE DATOS")
        data_source = st.selectbox(
            "Fuente activa:",
            ["Dataset Estándar (30 msgs)", "Discord Live (.jsonl)", "📂 Subir archivo JSON (Formato A)"],
            index=0,
            label_visibility="collapsed"
        )

        if data_source == "Dataset Estándar (30 msgs)":
            dataset = load_fixture_data()
        elif data_source == "Discord Live (.jsonl)":
            dataset = load_discord_raw_stream()
            if dataset is None:
                st.warning("No hay capturas en data/raw/. Usando dataset estándar como fallback.")
                dataset = load_fixture_data()
        else:
            dataset = None
            archivo = st.file_uploader("Lote JSON en Formato A (spec.md)", type=["json"])
            if archivo:
                try:
                    dataset = load_uploaded_json_file(archivo)
                    st.success(f"`{archivo.name}`: {len(dataset.interacciones)} mensajes")
                except ValueError as error:
                    st.error(str(error))
            else:
                st.info("Sube un archivo para comenzar.")

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

        if rol == "ADMIN":
            with st.expander("👤 Gestión de usuarios"):
                nuevo_usuario = st.text_input("Usuario", key="reg_usuario")
                nueva_clave = st.text_input("Contraseña", type="password", key="reg_clave")
                nuevo_rol = st.selectbox("Rol", ["CURATOR", "VIEWER", "ADMIN"], key="reg_rol")
                if st.button("Crear usuario", use_container_width=True):
                    if not (nuevo_usuario and nueva_clave):
                        st.warning("Completa el usuario y la contraseña.")
                    elif repository.register_user(nuevo_usuario, nueva_clave, role=nuevo_rol):
                        st.success(f"Usuario `{nuevo_usuario}` creado.")
                    else:
                        st.error("No se pudo crear el usuario (¿ya existe?).")

        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state["authenticated"] = False
            st.rerun()

    # Enrutamiento modular limpio
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