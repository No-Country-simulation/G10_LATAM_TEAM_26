"""
CommunityLab AI - Vista: Content Studio (Conectado directamente a Oracle Cloud)
"""
import streamlit as st
from src.ui.components.post_editor import render_linkedin_editor
from src.core.agents.strategist import generate_content_assets
from src.adapters.db.repository import get_high_value_opportunities
from src.domain.schemas import OpportunityType, GeneratedAssets, PostLinkedIn, DestaqueNewsletter


def render_studio_view():
    st.markdown('<div class="saas-title">Content Studio — Human-in-the-Loop</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Supervisión, ajuste editorial multiformato y aprobación previa a OCI.</div>', unsafe_allow_html=True)

    # 1. Leer oportunidades reales persistidas en Oracle Cloud
    oportunidades_oci = get_high_value_opportunities(min_score=0.70)

    if not oportunidades_oci:
        st.warning("No hay oportunidades de alto impacto registradas en Oracle Cloud. Ve a 'Detección & Scoring' y analiza un lote primero.")
        return

    st.success(f"Se recuperaron **{len(oportunidades_oci)}** oportunidades de alto impacto directamente desde Oracle Cloud.")

    # Selector con todas las oportunidades históricas de la BD
    options = [
        f"{msg.message_id} | {msg.author_anon} ({msg.opportunity_type} - Score {msg.opportunity_score:.2f})"
        for msg in oportunidades_oci
    ]
    selected_idx = st.selectbox("Selecciona una oportunidad para curar:", range(len(options)), format_func=lambda x: options[x])
    msg_seleccionado = oportunidades_oci[selected_idx]

    # Convertir tipo a Enum seguro
    try:
        op_enum = OpportunityType(msg_seleccionado.opportunity_type)
    except Exception:
        op_enum = OpportunityType.SUCCESS_STORY if msg_seleccionado.opportunity_score >= 0.90 else OpportunityType.FAQ

    # Estado del activo en memoria de sesión
    cache_key = f"assets_{msg_seleccionado.message_id}"
    if cache_key not in st.session_state:
        # Generar activo inicial para la oportunidad seleccionada
        st.session_state[cache_key] = generate_content_assets(
            clean_text=msg_seleccionado.clean_text,
            author=msg_seleccionado.author_anon,
            op_type=op_enum,
            reason=f"Mensaje evaluado con Score {msg_seleccionado.opportunity_score:.2f} en #{msg_seleccionado.channel}"
        )

    assets: GeneratedAssets = st.session_state[cache_key]

    # SECCIÓN INTERACTIVA: AJUSTE CON IA
    with st.expander("✨ Ajustar o Regenerar con IA (Human Feedback)", expanded=False):
        c_inst, c_btn = st.columns([3, 1])
        with c_inst:
            feedback_input = st.text_input(
                "Instrucción para la IA:", 
                placeholder="Ej: 'Hazlo más formal', 'Enfócate en la perseverancia'...",
                key=f"fb_{msg_seleccionado.message_id}"
            )
        with c_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Regenerar Activos", use_container_width=True, key=f"btn_regen_{msg_seleccionado.message_id}"):
                with st.spinner("La IA está refinando el copy con tu feedback..."):
                    st.session_state[cache_key] = generate_content_assets(
                        clean_text=msg_seleccionado.clean_text,
                        author=msg_seleccionado.author_anon,
                        op_type=op_enum,
                        reason=f"Ajuste solicitado por editor humano",
                        feedback_usuario=feedback_input
                    )
                st.rerun()

    # TABS MULTIFORMATO
    tab_linkedin, tab_newsletter, tab_faq = st.tabs([
        "📱 Publicación LinkedIn", 
        "📰 Destaque Newsletter", 
        "💡 FAQ / Mentoría"
    ])

    with tab_linkedin:
        if assets.post_linkedin:
            post = assets.post_linkedin
            approved, rejected, ed_title, ed_copy = render_linkedin_editor(
                msg_id=msg_seleccionado.message_id,
                author=msg_seleccionado.author_anon,
                default_title=post.titulo,
                default_copy=post.texto_copy
            )

            if approved:
                st.session_state["approved_posts"][msg_seleccionado.message_id] = {
                    "post_id": f"POST-{msg_seleccionado.message_id[-6:]}",
                    "tipo": "LINKEDIN",
                    "title": ed_title,
                    "copy": ed_copy,
                    "author": msg_seleccionado.author_anon,
                    "origin_msg_id": msg_seleccionado.message_id,
                    "score": msg_seleccionado.opportunity_score,
                    "status": "APPROVED_FOR_OCI"
                }
                st.toast(f"✅ Post para {msg_seleccionado.message_id} aprobado.", icon="🎉")

            if rejected:
                if msg_seleccionado.message_id in st.session_state["approved_posts"]:
                    del st.session_state["approved_posts"][msg_seleccionado.message_id]
                st.toast(f"🚫 Activo {msg_seleccionado.message_id} descartado.", icon="⚠️")

    with tab_newsletter:
        with st.container(border=True):
            st.markdown("##### 📰 Destaque para el Boletín Semanal")
            titular_def = assets.destaque_newsletter_semanal.titular if assets.destaque_newsletter_semanal else f"Logro destacado: {msg_seleccionado.author_anon}"
            resumen_def = assets.destaque_newsletter_semanal.resumen if assets.destaque_newsletter_semanal else msg_seleccionado.clean_text[:140]

            news_titular = st.text_input("Titular de la Newsletter", value=titular_def, key=f"n_t_{msg_seleccionado.message_id}")
            news_resumen = st.text_area("Resumen Informativo", value=resumen_def, height=120, key=f"n_r_{msg_seleccionado.message_id}")

            if st.button("✅ Aprobar para Newsletter", key=f"btn_n_app_{msg_seleccionado.message_id}", type="primary", use_container_width=True):
                st.session_state["approved_posts"][f"NEWS-{msg_seleccionado.message_id}"] = {
                    "post_id": f"NEWS-{msg_seleccionado.message_id[-6:]}",
                    "tipo": "NEWSLETTER",
                    "title": news_titular,
                    "copy": news_resumen,
                    "author": msg_seleccionado.author_anon,
                    "origin_msg_id": msg_seleccionado.message_id,
                    "score": msg_seleccionado.opportunity_score,
                    "status": "APPROVED_FOR_OCI"
                }
                st.toast(f"✅ Newsletter aprobada para {msg_seleccionado.message_id}.", icon="📰")

    with tab_faq:
        with st.container(border=True):
            st.markdown("##### 💡 Base de Conocimiento y FAQ")
            tema_faq = f"Tip Rápido sobre #{msg_seleccionado.channel}"
            ed_faq_tema = st.text_input("Tema de la FAQ", value=tema_faq, key=f"faq_t_{msg_seleccionado.message_id}")
            ed_faq_detalle = st.text_area("Detalle / Consulta", value=msg_seleccionado.clean_text, height=120, key=f"faq_d_{msg_seleccionado.message_id}")

            if st.button("✅ Aprobar como FAQ Oficial", key=f"btn_faq_app_{msg_seleccionado.message_id}", type="primary", use_container_width=True):
                st.session_state["approved_posts"][f"FAQ-{msg_seleccionado.message_id}"] = {
                    "post_id": f"FAQ-{msg_seleccionado.message_id[-6:]}",
                    "tipo": "FAQ_EDUCATIVA",
                    "title": ed_faq_tema,
                    "copy": ed_faq_detalle,
                    "author": msg_seleccionado.author_anon,
                    "origin_msg_id": msg_seleccionado.message_id,
                    "score": msg_seleccionado.opportunity_score,
                    "status": "APPROVED_FOR_OCI"
                }
                st.toast(f"✅ FAQ guardada para {msg_seleccionado.message_id}.", icon="📚")