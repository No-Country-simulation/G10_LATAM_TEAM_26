# =====================================
# IMPORTAR LIBRERÍAS
# =====================================

# Streamlit para la interfaz
import streamlit as st

if not st.session_state.get("autenticado", False):

    st.switch_page("app.py")
# Librería para leer JSON
import json


# =====================================
# CARGAR JSON
# =====================================

# Abrimos el archivo de datos
with open("data/mock_data.json", "r", encoding="utf-8") as archivo:

    # Convertimos JSON en lista Python
    datos = json.load(archivo)


# =====================================
# TITULO
# =====================================

st.title("✍️ Contenido Generado")

st.write(
    "Activos generados automáticamente por CommunityLab."
)


# =====================================
# SELECTOR DE OPORTUNIDAD
# =====================================

# Crear lista con IDs
ids = [item["id"] for item in datos]

# Selector desplegable
id_seleccionado = st.selectbox(
    "Seleccionar oportunidad",
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
# INFORMACIÓN GENERAL
# =====================================

st.subheader("Información")

st.write(
    f"Tipo: {registro['type']}"
)

st.write(
    f"Canal: {registro['channel']}"
)

st.write(
    f"Mensaje original: {registro['message']}"
)

st.divider()


# =====================================
# PESTAÑAS
# =====================================

tab1, tab2, tab3 = st.tabs(
    [
        "📣 LinkedIn",
        "📧 Newsletter",
        "❓ FAQ"
    ]
)


# =====================================
# LINKEDIN
# =====================================

with tab1:

    if registro["linkedin"]:

        st.text_area(
            "Post para LinkedIn",
            registro["linkedin"],
            height=250
        )

    else:

        st.info(
            "No hay contenido LinkedIn disponible."
        )


# =====================================
# NEWSLETTER
# =====================================

with tab2:

    if registro["newsletter"]:

        st.text_area(
            "Newsletter",
            registro["newsletter"],
            height=250
        )

    else:

        st.info(
            "No hay newsletter disponible."
        )


# =====================================
# FAQ
# =====================================

with tab3:

    if registro["faq"]:

        st.text_area(
            "FAQ",
            registro["faq"],
            height=250
        )

    else:

        st.info(
            "No hay FAQ disponible."
        )


# =====================================
# CURADURÍA HUMANA
# =====================================

st.divider()

st.subheader("Curaduría Humana")

col1, col2, col3 = st.columns(3)

with col1:
    st.button("✅ Aprobar")

with col2:
    st.button("✏️ Editar")

with col3:
    st.button("❌ Rechazar")