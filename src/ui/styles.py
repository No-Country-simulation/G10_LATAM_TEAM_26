"""
CommunityLab AI - Adaptive Enterprise Design System
"""
import streamlit as st


def apply_enterprise_theme():
    custom_css = """
    <style>
    /* 1. FUENTE CORPORATIVA MODERNA */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"], .stMarkdown, p, h1, h2, h3, h4, h5, button {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    /* 2. HEADER: Transparente para que coincida con el fondo, manteniendo el menú de 3 puntos (Settings / Themes) */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
    
    /* Ocultar únicamente el botón Deploy */
    .stDeployButton {
        display: none !important;
    }

    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 1250px !important;
    }

    /* 3. TÍTULOS ENTERPRISE */
    .saas-title {
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin-bottom: 0.2rem;
    }
    .saas-subtitle {
        font-size: 0.95rem;
        color: #64748B;
        font-weight: 500;
        margin-bottom: 1.8rem;
    }

    /* 4. KPI CARDS */
    .kpi-container {
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-radius: 14px;
        padding: 1.25rem 1.4rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.04);
        background: rgba(255, 255, 255, 0.05);
    }
    .kpi-label {
        font-size: 0.76rem;
        font-weight: 700;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .kpi-number {
        font-size: 2.2rem;
        font-weight: 800;
        line-height: 1.1;
        margin: 0.35rem 0;
    }
    .kpi-trend {
        font-size: 0.78rem;
        font-weight: 600;
        color: #10B981;
    }

    /* 5. PILLS / BADGES DE ESTADO */
    .pill {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        font-size: 0.72rem;
        font-weight: 700;
        border-radius: 6px;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }
    .pill-success { background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; }
    .pill-faq { background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; }
    .pill-milestone { background: #FAF5FF; color: #7E22CE; border: 1px solid #E9D5FF; }
    .pill-feedback { background: #FFFBEB; color: #B45309; border: 1px solid #FDE68A; }
    .pill-neutral { background: #F1F5F9; color: #475569; border: 1px solid #E2E8F0; }

    /* 6. SOCIAL CARD LINKEDIN (Fiel a la interfaz real) */
    .linkedin-card {
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.5rem;
        background: #FFFFFF;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
    .linkedin-card-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 1rem;
    }
    .linkedin-avatar {
        width: 44px;
        height: 44px;
        background: #0A66C2;
        color: white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.95rem;
    }
    .linkedin-title-text {
        font-weight: 700;
        font-size: 0.95rem;
        color: #0F172A;
        margin-bottom: 0.4rem;
    }
    .linkedin-body-text {
        font-size: 0.90rem;
        line-height: 1.6;
        color: #334155;
        white-space: pre-wrap;
    }

    /* 7. BOTONES DE NAVEGACIÓN DEL SIDEBAR */
    div[data-testid="stSidebar"] button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        text-align: left !important;
        padding: 0.5rem 0.75rem !important;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)