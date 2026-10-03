"""
CommunityLab AI - Human-in-the-Loop LinkedIn Post Editor
"""
import html

import streamlit as st


def render_linkedin_editor(msg_id: str, author: str, default_title: str, default_copy: str):
    """
    Editor con vista previa de tarjeta LinkedIn en tiempo real.
    """
    col_edit, col_preview = st.columns([1, 1], gap="large")

    with col_edit:
        st.markdown("##### ✏️ Editor de Curaduría Editorial")
        edited_title = st.text_input(
            "Título del Activo / Hook de LinkedIn", 
            value=default_title, 
            key=f"title_{msg_id}"
        )
        edited_copy = st.text_area(
            "Copy para Publicación", 
            value=default_copy, 
            height=280, 
            key=f"copy_{msg_id}"
        )
        st.caption("Verifica el tono corporativo, los hashtags y el llamado a la acción antes de persistir.")
        
        c1, c2 = st.columns(2)
        approved = c1.button("✅ Aprobar para OCI", key=f"btn_app_{msg_id}", use_container_width=True, type="primary")
        rejected = c2.button("🚫 Descartar", key=f"btn_rej_{msg_id}", use_container_width=True)

    with col_preview:
        st.markdown("##### 👁️ Previsualización de LinkedIn")
        # Renderizado limpio con tarjeta blanca estilizada
        html_preview = f"""<div class="linkedin-card">
    <div class="linkedin-card-header">
        <div class="linkedin-avatar">CL</div>
        <div>
            <div style="font-weight: 700; font-size: 0.92rem; color: #0F172A;">CommunityLab Oficial</div>
            <div style="font-size: 0.75rem; color: #64748B;">Comunidad Digital • Oracle Next Education & Alura</div>
        </div>
    </div>
    <div class="linkedin-title-text">{html.escape(edited_title)}</div>
    <div class="linkedin-body-text">{html.escape(edited_copy).replace(chr(10), "<br>")}</div>
</div>"""
        st.markdown(html_preview, unsafe_allow_html=True)

    return approved, rejected, edited_title, edited_copy