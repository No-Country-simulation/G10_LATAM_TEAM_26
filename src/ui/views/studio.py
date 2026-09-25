"""
CommunityLab AI - Vista: Content Studio (Curaduría Multiformato)
Permite curar Post de LinkedIn, Destaques de Newsletter y FAQs Educativas.
"""
import streamlit as st
from src.ui.components.post_editor import render_linkedin_editor
from src.core.agents.strategist import generate_content_assets


def render_studio_view():
    st.markdown('<div class="saas-title">Content Studio — Human-in-the-Loop</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Supervisión, ajuste editorial multiformato y aprobación previa a OCI.</div>', unsafe_allow_html=True)

    processed = st.session_state.get("processed_results", [])
    high_value = [item for item in processed if item[1] is not None]

    if not high_value:
        st.warning("No hay oportunidades listas. Ve a 'Detección & Scoring' y ejecuta el análisis primero.")
        return

    st.success(f"Se detectaron **{len(high_value)}** oportunidades de alto impacto listas para curaduría.")

    # Selector de oportunidad
    options = [
        f"{p.message_id} | {p.autor_anonimizado} ({p.opportunity.type.value} - Score {p.opportunity.opportunity_score:.2f})"
        for p, a in high_value
    ]
    selected_idx = st.selectbox("Selecciona una oportunidad para revisar:", range(len(options)), format_func=lambda x: options[x])
    proc, assets = high_value[selected_idx]

    # SECCIÓN INTERACTIVA: AJUSTE CON IA
    with st.expander("✨ Ajustar o Regenerar con IA (Human Feedback)", expanded=False):
        c_inst, c_btn = st.columns([3, 1])
        with c_inst:
            feedback_input = st.text_input(
                "Instrucción para la IA:", 
                placeholder="Ej: 'Hazlo más formal', 'Enfócate en el cambio de carrera', 'Añade un llamado a la acción'...",
                key=f"fb_{proc.message_id}"
            )
        with c_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Regenerar Activos", use_container_width=True, key=f"btn_regen_{proc.message_id}"):
                with st.spinner("La IA está refinando el copy con tu feedback..."):
                    new_assets = generate_content_assets(
                        clean_text=proc.texto_limpio,
                        author=proc.autor_anonimizado,
                        op_type=proc.opportunity.type,
                        reason=proc.opportunity.reason,
                        feedback_usuario=feedback_input
                    )
                    high_value[selected_idx] = (proc, new_assets)
                    assets = new_assets
                st.rerun()

    # TABS MULTIFORMATO (REQUISITO HACKATHON)
    tab_linkedin, tab_newsletter, tab_faq = st.tabs([
        "📱 Publicación LinkedIn", 
        "📰 Destaque Newsletter", 
        "💡 FAQ / Mentoría"
    ])

    # 1. FORMATO LINKEDIN
    with tab_linkedin:
        if assets.post_linkedin:
            post = assets.post_linkedin
            approved, rejected, ed_title, ed_copy = render_linkedin_editor(
                msg_id=proc.message_id,
                author=proc.autor_anonimizado,
                default_title=post.titulo,
                default_copy=post.texto_copy
            )

            if approved:
                st.session_state["approved_posts"][proc.message_id] = {
                    "post_id": f"POST-{proc.message_id.replace('MSG-', '').replace('DISC-', '')}",
                    "tipo": "LINKEDIN",
                    "title": ed_title,
                    "copy": ed_copy,
                    "author": proc.autor_anonimizado,
                    "origin_msg_id": proc.message_id,
                    "score": proc.opportunity.opportunity_score,
                    "status": "APPROVED_FOR_OCI"
                }
                st.toast(f"✅ Post para {proc.message_id} aprobado.", icon="🎉")

            if rejected:
                if proc.message_id in st.session_state["approved_posts"]:
                    del st.session_state["approved_posts"][proc.message_id]
                st.toast(f"🚫 Activo {proc.message_id} descartado.", icon="⚠️")
        else:
            st.info("No se generó borrador de LinkedIn para esta interacción.")

    # 2. FORMATO NEWSLETTER
    with tab_newsletter:
        with st.container(border=True):
            st.markdown("##### 📰 Destaque para el Boletín Semanal de la Comunidad")
            titular_default = assets.destaque_newsletter_semanal.titular if assets.destaque_newsletter_semanal else f"Logro destacado: {proc.autor_anonimizado}"
            resumen_default = assets.destaque_newsletter_semanal.resumen if assets.destaque_newsletter_semanal else proc.texto_limpio[:140]

            news_titular = st.text_input("Titular de la Newsletter", value=titular_default, key=f"n_t_{proc.message_id}")
            news_resumen = st.text_area("Cuerpo / Resumen Informativo", value=resumen_default, height=120, key=f"n_r_{proc.message_id}")
            
            c_a, c_b = st.columns(2)
            if c_a.button("✅ Aprobar para Newsletter", key=f"btn_n_app_{proc.message_id}", type="primary", use_container_width=True):
                st.session_state["approved_posts"][f"NEWS-{proc.message_id}"] = {
                    "post_id": f"NEWS-{proc.message_id.replace('MSG-', '').replace('DISC-', '')}",
                    "tipo": "NEWSLETTER",
                    "title": news_titular,
                    "copy": news_resumen,
                    "author": proc.autor_anonimizado,
                    "origin_msg_id": proc.message_id,
                    "score": proc.opportunity.opportunity_score,
                    "status": "APPROVED_FOR_OCI"
                }
                st.toast(f"✅ Newsletter para {proc.message_id} aprobada.", icon="📰")

    # 3. FORMATO FAQ / RECURSO EDUCATIVO
    with tab_faq:
        with st.container(border=True):
            st.markdown("##### 💡 Base de Conocimiento y Guía de Mentoría")
            tema_faq = f"Tip Rápido: Solución a duda recurrente en #{proc.channel}"
            ed_faq_tema = st.text_input("Tema de la FAQ", value=tema_faq, key=f"faq_t_{proc.message_id}")
            ed_faq_detalle = st.text_area("Pregunta Original / Caso Técnico", value=proc.texto_limpio, height=120, key=f"faq_d_{proc.message_id}")

            if st.button("✅ Aprobar como FAQ Oficial", key=f"btn_faq_app_{proc.message_id}", type="primary", use_container_width=True):
                st.session_state["approved_posts"][f"FAQ-{proc.message_id}"] = {
                    "post_id": f"FAQ-{proc.message_id.replace('MSG-', '').replace('DISC-', '')}",
                    "tipo": "FAQ_EDUCATIVA",
                    "title": ed_faq_tema,
                    "copy": ed_faq_detalle,
                    "author": proc.autor_anonimizado,
                    "origin_msg_id": proc.message_id,
                    "score": proc.opportunity.opportunity_score,
                    "status": "APPROVED_FOR_OCI"
                }
                st.toast(f"✅ FAQ para {proc.message_id} archivada.", icon="📚")