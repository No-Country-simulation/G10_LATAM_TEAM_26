# ==========================================
# IMPORTAR STREAMLIT
# ==========================================

# Librería principal para la interfaz
import streamlit as st

if not st.session_state.get("autenticado", False):

    st.switch_page("app.py")
# ==========================================
# TITULO DE LA PAGINA
# ==========================================

st.title("🚨 Motor de Decisiones")

st.write(
    "Recomendaciones automáticas generadas por CommunityLab."
)

st.divider()


# ==========================================
# ALERTA DE RIESGO
# ==========================================

st.subheader("🚨 Riesgo Detectado")

st.error(
    """
    Usuario: ana_123

    Actividad reducida un 75%.

    Sentimiento detectado:
    NEGATIVO

    Acción sugerida:
    Asignar mentor.
    """
)


# ==========================================
# TENDENCIA DETECTADA
# ==========================================

st.subheader("📈 Tendencia Detectada")

st.warning(
    """
    Tema:

    OCI Foundations

    Incremento de consultas:
    +63%

    Acción sugerida:

    Crear webinar o contenido educativo.
    """
)


# ==========================================
# CASO DE EXITO
# ==========================================

st.subheader("🏆 Oportunidad Comunitaria")

st.success(
    """
    SUCCESS STORY detectada.

    Estudiante consiguió empleo.

    Acción recomendada:

    Generar LinkedIn Post.
    """
)


# ==========================================
# RECOMENDACIONES
# ==========================================

st.subheader("✅ Acciones Recomendadas")

st.checkbox("Crear FAQ sobre OCI")
st.checkbox("Crear Webinar OCI")
st.checkbox("Programar mentoría")
st.checkbox("Generar post LinkedIn")