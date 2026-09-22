# ==================================================
# IMPORTAR LIBRERÍA
# ==================================================

import streamlit as st

# ==================================================
# CONFIGURACIÓN GENERAL
# ==================================================

st.set_page_config(
    page_title="CommunityLab",
    page_icon="🚀",
    layout="wide"
)

# ==================================================
# ESTILOS PERSONALIZADOS
# ==================================================

st.markdown("""
<style>

/* Fondo general */
.stApp{
    background: linear-gradient(
        180deg,
        #020617 0%,
        #0F172A 100%
    );
}

/* Sidebar */
section[data-testid="stSidebar"]{
    background:#111827;
}

/* Reducir ancho máximo */
.block-container{
    max-width: 1200px;
    padding-top: 2rem;
}

/* Hero principal */
.hero-title{
    font-size:58px;
    font-weight:800;
    line-height:1.1;

    background: linear-gradient(
        90deg,
        #3B82F6,
        #06B6D4
    );

    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
}

.hero-subtitle{
    font-size:22px;
    color:#94A3B8;
    margin-top:-10px;
    margin-bottom:30px;
}

/* Tarjeta principal */
.hero-card{

    background: linear-gradient(
        135deg,
        #111827,
        #1E293B
    );

    border:1px solid #334155;

    border-radius:22px;

    padding:35px;

    margin-bottom:20px;
}

/* KPIs */
[data-testid="metric-container"]{

    background: linear-gradient(
        135deg,
        #111827,
        #1E293B
    );

    border:1px solid #334155;

    border-radius:18px;

    padding:15px;

    box-shadow:
        0px 4px 15px rgba(0,0,0,.20);
}

/* Hover KPI */
[data-testid="metric-container"\]:hover{
    border:1px solid #3B82F6;
}

/* Encabezados */
h2,h3{
    color:white !important;
}

</style>
""", unsafe_allow_html=True)

# ==================================================
# SIDEBAR
# ==================================================

with st.sidebar:

   

    st.divider()

    st.success("🟢 Sistema Activo")

    st.caption(
        "Community Intelligence Platform"
    )

# ==================================================
# HERO
# ==================================================

st.markdown("""
<div class="hero-title">

CommunityLab

</div>

<div class="hero-subtitle">

Transformando conversaciones en oportunidades,
contenido y decisiones inteligentes.

</div>
""", unsafe_allow_html=True)

# =================================================
# TARJETA PRINCIPAL
# ==================================================

st.markdown("""
<div class="hero-card">

<h2>
🚀 Motor Inteligente de Transformación y Distribución
</h2>

<p style="
font-size:18px;
line-height:1.8;
color:#CBD5E1;
">

CommunityLab analiza conversaciones provenientes de
Discord, Slack, foros y formularios.

Detecta oportunidades de alto valor, genera contenido
para marketing y facilita decisiones basadas en datos
mediante inteligencia artificial.

</p>

</div>
""", unsafe_allow_html=True)

# ==================================================
# KPIs
# ==================================================

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "💬 Mensajes",
        "12,450"
    )

with col2:

    st.metric(
        "🎯 Oportunidades",
        "324"
    )

with col3:

    st.metric(
        "📣 Activos",
        "98"
    )

with col4:

    st.metric(
        "🚨 Alertas",
        "12"
    )

# ==================================================
# CAPACIDADES
# ==================================================

st.write("")
st.subheader("🎯 Capacidades")

c1, c2, c3 = st.columns(3)

with c1:

    st.info("🤖 Análisis IA")
    st.info("📊 Clasificación Semántica")

with c2:

    st.info("📣 LinkedIn Posts")
    st.info("📧 Newsletters")

with c3:

    st.info("❓ FAQs Inteligentes")
    st.info("🚨 Motor de Decisiones")

# ==================================================
# FLUJO
# ==================================================

st.write("")
st.subheader("🔄 Flujo de Procesamiento")

f1, f2, f3, f4, f5 = st.columns(5)

with f1:
    st.metric("📥", "Ingesta")

with f2:
    st.metric("🤖", "Análisis")

with f3:
    st.metric("🎯", "Oportunidad")

with f4:
    st.metric("📣", "Contenido")

with f5:
    st.metric("☁️", "OCI")