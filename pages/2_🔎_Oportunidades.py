# =====================================
# IMPORTAR LIBRERÍAS
# =====================================

# Streamlit para la interfaz
import streamlit as st

if not st.session_state.get("autenticado", False):

    st.switch_page("app.py")
# Librería para trabajar con JSON
import json


# =====================================
# CARGAR DATOS DEL JSON
# =====================================

# Abrimos el archivo JSON
with open("data/mock_data.json", "r", encoding="utf-8") as archivo:

    # Convertimos el JSON en una lista de Python
    oportunidades = json.load(archivo)


# =====================================
# TITULO DE LA PÁGINA
# =====================================

st.title("🔎 Oportunidades Detectadas")

st.write(
    "Mensajes que CommunityLab considera relevantes para marketing y comunidad."
)


# =====================================
# FILTRO POR TIPO
# =====================================

# Obtener todos los tipos únicos
tipos = list(
    set(
        item["type"]
        for item in oportunidades
    )
)

# Agregamos la opción Todos
tipos.insert(0, "TODOS")

# Selector desplegable
tipo_seleccionado = st.selectbox(
    "Filtrar por tipo",
    tipos
)


# =====================================
# CONTADOR
# =====================================

st.metric(
    "Oportunidades encontradas",
    len(oportunidades)
)


st.divider()


# =====================================
# RECORRER OPORTUNIDADES
# =====================================

for oportunidad in oportunidades:

    # Aplicar filtro
    if (
        tipo_seleccionado != "TODOS"
        and oportunidad["type"] != tipo_seleccionado
    ):
        continue


    # =====================================
    # ICONOS SEGÚN TIPO
    # =====================================

    icono = "📌"

    if oportunidad["type"] == "SUCCESS_STORY":
        icono = "🏆"

    elif oportunidad["type"] == "FAQ":
        icono = "❓"

    elif oportunidad["type"] == "TREND":
        icono = "📈"

    elif oportunidad["type"] == "FEEDBACK":
        icono = "🚨"


    # =====================================
    # TARJETA VISUAL
    # =====================================

    with st.container(border=True):

        # Tipo de oportunidad
        st.subheader(
            f"{icono} {oportunidad['type']}"
        )

        # Score
        st.write(
            f"Score de oportunidad: {int(oportunidad['score'] * 100)}%"
        )

        # Barra visual
        st.progress(
            oportunidad["score"]
        )

        # Mensaje original
        st.write(
            oportunidad["message"]
        )

        # Canal de origen
        st.caption(
            f"Canal: #{oportunidad['channel']}"
        )

        # Temas detectados
        st.write(
            f"Temas: {', '.join(oportunidad['topics'])}"
        )

        # Sentimiento detectado
        st.info(
            f"Sentimiento: {oportunidad['sentiment']}"
        )

        # Botón futuro
        st.button(
            "Ver contenido generado",
            key=oportunidad["id"]
        )