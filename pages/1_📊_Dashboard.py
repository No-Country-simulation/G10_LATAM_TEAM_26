# Importamos Streamlit para construir la interfaz
import streamlit as st



if not st.session_state.get("autenticado", False):

    st.switch_page("app.py")
# Título principal de la página
st.title("📊 Dashboard")

# Texto descriptivo
st.write(
    "Resumen general de la actividad de la comunidad."
)

# Creamos 4 columnas para mostrar KPIs
col1, col2, col3, col4 = st.columns(4)

# KPI 1
with col1:
    st.metric(
        label="Mensajes Analizados",
        value="12,450"
    )

# KPI 2
with col2:
    st.metric(
        label="Oportunidades",
        value="324"
    )

# KPI 3
with col3:
    st.metric(
        label="Contenido Generado",
        value="98"
    )

# KPI 4
with col4:
    st.metric(
        label="Alertas Activas",
        value="12"
    )

# Línea divisoria visual
st.divider()

# Encabezado para la siguiente sección
st.subheader("🎯 Estado del Sistema")

# Tarjeta informativa
st.success(
    "CommunityLab está procesando conversaciones correctamente."
)