# =====================================
# IMPORTAR LIBRERÍAS
# =====================================

# Streamlit para la interfaz
import streamlit as st
if not st.session_state.get("autenticado", False):

    st.switch_page("app.py")
# JSON para leer los datos
import json


# =====================================
# CARGAR DATOS
# =====================================

# Abrimos el archivo JSON
with open("data/mock_data.json", "r", encoding="utf-8") as archivo:

    # Convertimos JSON a lista Python
    datos = json.load(archivo)


# =====================================
# TITULO
# =====================================

st.title("🔗 Trazabilidad")

st.write(
    "Seguimiento completo desde el mensaje original hasta el contenido generado."
)

st.divider()


# =====================================
# SELECTOR
# =====================================

# Obtener todos los IDs
ids = [item["id"] for item in datos]

# Mostrar lista desplegable
id_seleccionado = st.selectbox(
    "Seleccionar mensaje",
    ids
)


# =====================================
# BUSCAR REGISTRO
# =====================================

registro = next(
    item
    for item in datos
    if item["id"] == id_seleccionado
)


# =====================================
# MOSTRAR FLUJO
# =====================================

st.subheader("Flujo de Transformación")

st.code(
    f"""
MENSAJE: {registro['id']}
       ↓
OPORTUNIDAD: {registro['type']}
       ↓
ACTIVO GENERADO
"""
)


# =====================================
# MENSAJE ORIGINAL
# =====================================

st.subheader("💬 Mensaje Original")

st.info(
    registro["message"]
)


# =====================================
# METADATOS
# =====================================

# Creamos 3 columnas para mostrar información
col1, col2, col3 = st.columns(3)

# Canal
with col1:
    st.metric(
        "Canal",
        registro["channel"]
    )

# Sentimiento
with col2:
    st.metric(
        "Sentimiento",
        registro["sentiment"]
    )

# Score de oportunidad
with col3:
    st.metric(
        "Score",
        f"{int(registro['score'] * 100)}%"
    )


# =====================================
# TEMAS DETECTADOS
# =====================================

st.subheader("🏷️ Temas Detectados")

for tema in registro["topics"]:

    st.write(
        f"• {tema}"
    )


# =====================================
# ACCIÓN IA
# =====================================

st.subheader("🤖 Acción de CommunityLab")

if registro["type"] == "SUCCESS_STORY":

    st.success(
        "Generar caso de éxito y publicación para LinkedIn."
    )

elif registro["type"] == "FAQ":

    st.warning(
        "Generar artículo FAQ para la comunidad."
    )

elif registro["type"] == "TREND":

    st.info(
        "Generar resumen de tendencia para newsletter."
    )

else:

    st.write(
        "Sin acción definida."
    )