# ==================================================
# LOGIN COMMUNITYLAB
# ==================================================

import streamlit as st

# ==================================================
# CONFIGURACIÓN
# ==================================================

st.set_page_config(
    page_title="CommunityLab Login",
    page_icon="🔐",
    layout="centered"
)

# ==================================================
# SI YA ESTÁ AUTENTICADO
# REDIRIGIR AL HOME
# ==================================================

if st.session_state.get("autenticado", False):

    st.switch_page("pages/0_Home.py")

# ==================================================
# OCULTAR SIDEBAR Y NAVEGACIÓN
# ==================================================

st.markdown("""
<style>

/* Ocultar navegación automática */
section[data-testid="stSidebarNav"]{
    display:none;
}

/* Ocultar sidebar completo */
section[data-testid="stSidebar"]{
    display:none;
}

</style>
""", unsafe_allow_html=True)



# ==================================================
# TITULO
# ==================================================

st.title("🔐 Iniciar Sesión")

st.write(
    "Ingrese sus credenciales para acceder a CommunityLab."
)

# ==================================================
# FORMULARIO
# ==================================================

usuario = st.text_input(
    "Usuario"
)

password = st.text_input(
    "Contraseña",
    type="password"
)

# ==================================================
# LOGIN
# ==================================================

if st.button("Ingresar"):

    if usuario == "admin" and password == "123456":

        # Guardar sesión
        st.session_state["autenticado"] = True
        st.session_state["usuario"] = usuario

        st.success(
            "Acceso concedido ✅"
        )

        st.switch_page(
            "pages/0_Home.py"
        )

    else:

        st.error(
            "Usuario o contraseña incorrectos."
        )