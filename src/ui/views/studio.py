"""
CommunityLab AI - Vista: Content Studio (Human-in-the-Loop con Imágenes Persistidas)
"""
from pathlib import Path
import streamlit as st
from src.ui.components.post_editor import render_linkedin_editor
from src.core.agents.strategist import generate_content_assets
from src.adapters.db.repository import get_high_value_opportunities
from src.adapters.imagenes import generar
from src.domain.schemas import OpportunityType, GeneratedAssets
import urllib.parse
import io
import zipfile


def render_studio_view():
    st.markdown('<div class="saas-title">Content Studio — Human-in-the-Loop</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Supervisión, ajuste editorial multiformato y persistencia multimedia.</div>', unsafe_allow_html=True)

    # 1. Detectar la fuente activa seleccionada por el usuario
    dataset = st.session_state.get("dataset")
    source_activo = dataset.interacciones[0].source if dataset and dataset.interacciones else "discord"

    # 2. Recuperar oportunidades de OCI ÚNICAMENTE para esta fuente activa
    oportunidades_oci = get_high_value_opportunities(min_score=0.70, source=source_activo)

    if not oportunidades_oci:
        st.warning(f"No hay oportunidades de alto impacto para la fuente '{source_activo}' en Oracle Cloud. Ve a 'Detección & Scoring' y analiza un lote primero.")
        return

    st.success(f"Se recuperaron **{len(oportunidades_oci)}** oportunidades ({source_activo}) directamente desde Oracle Cloud.")

    options = [
        f"{msg.message_id} | {msg.author_anon} ({msg.opportunity_type} - Score {msg.opportunity_score:.2f})"
        for msg in oportunidades_oci
    ]
    selected_idx = st.selectbox("Selecciona una oportunidad para curar:", range(len(options)), format_func=lambda x: options[x])
    msg_seleccionado = oportunidades_oci[selected_idx]

    try:
        op_enum = OpportunityType(msg_seleccionado.opportunity_type)
    except Exception:
        op_enum = OpportunityType.SUCCESS_STORY if msg_seleccionado.opportunity_score >= 0.90 else OpportunityType.FAQ

    cache_key = f"assets_{msg_seleccionado.message_id}"
    if cache_key not in st.session_state:
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
                        reason="Ajuste solicitado por editor humano",
                        feedback_usuario=feedback_input
                    )
                st.rerun()

    # TABS MULTIFORMATO
    tab_linkedin, tab_newsletter, tab_faq = st.tabs([
        "📱 Publicación LinkedIn", 
        "📰 Destaque Newsletter", 
        "💡 FAQ / Mentoría"
    ])

# 1. PESTAÑA LINKEDIN
    with tab_linkedin:
        if assets.post_linkedin:
            post = assets.post_linkedin
            
            # --- 1. EDITOR Y PREVISUALIZACIÓN DE LINKEDIN ---
            approved, rejected, ed_title, ed_copy = render_linkedin_editor(
                msg_id=msg_seleccionado.message_id,
                author=msg_seleccionado.author_anon,
                default_title=post.titulo,
                default_copy=post.texto_copy
            )

            # Rutas y claves para la imagen
            img_key_li = f"img_{msg_seleccionado.message_id}_li"
            img_dir = Path("data/processed/generated/images")
            img_dir.mkdir(parents=True, exist_ok=True)
            saved_img_path = img_dir / f"{msg_seleccionado.message_id}.png"

            # --- 2. BANNER GRÁFICO (FLUX / POLLINATIONS) ---
            with st.container(border=True):
                st.markdown("##### 🎨 Banner Gráfico para Redes (Pollinations AI - Flux)")
                c_img1, c_img2 = st.columns([1.2, 1.8])
                
                with c_img1:
                    if msg_seleccionado.opportunity_type == "SUCCESS_STORY":
                        prompt_sugerido = "Isometric 3D illustration of a triumphant developer workstation, glowing laptop showing code, golden trophy, celebratory tech confetti, clean modern studio lighting, vibrant colors"
                    elif msg_seleccionado.opportunity_type == "FAQ":
                        prompt_sugerido = "Minimalist 3D tech tutorial concept, floating server nodes connected by light rays, cloud architecture puzzle, soft blue lighting"
                    else:
                        prompt_sugerido = "Modern tech feedback diagram, 3D star rating floating above futuristic tablet, sleek office background"

                    prompt_img = st.text_area("Prompt de Imagen (en inglés):", value=prompt_sugerido, height=100, key=f"p_li_{msg_seleccionado.message_id}")
                    
                    if st.button("🖼️ Generar Banner LinkedIn", key=f"b_li_{msg_seleccionado.message_id}", type="secondary", use_container_width=True):
                        with st.spinner("Generando banner contextualizado con Flux..."):
                            try:
                                img_bytes, ext = generar(prompt_img, formato="post_linkedin")
                                st.session_state[img_key_li] = img_bytes
                                with open(saved_img_path, "wb") as f:
                                    f.write(img_bytes)
                                st.success(f"Imagen guardada en: `{saved_img_path.name}`")
                            except Exception as e:
                                st.error(f"Error generando imagen: {e}")

                with c_img2:
                    # Cargar desde disco si no está en sesión
                    if saved_img_path.exists() and img_key_li not in st.session_state:
                        with open(saved_img_path, "rb") as f:
                            st.session_state[img_key_li] = f.read()

                    if img_key_li in st.session_state:
                        st.image(st.session_state[img_key_li], caption=f"Banner 1200x627 para {msg_seleccionado.message_id}", use_container_width=True)
                        st.download_button(
                            label="💾 Descargar Banner PNG",
                            data=st.session_state[img_key_li],
                            file_name=f"banner-{msg_seleccionado.message_id}.png",
                            mime="image/png",
                            use_container_width=True
                        )
                    else:
                        st.info("Presiona 'Generar Banner' para crear la ilustración 3D adaptada a este logro.")

            # --- 3. HERRAMIENTAS DE DISTRIBUCIÓN INMEDIATA (PRESS KIT & SHARE LINKEDIN) ---
            with st.container(border=True):
                st.markdown("##### 🚀 Distribución Lista para Publicar")
                c_dist1, c_dist2, c_dist3 = st.columns([1.2, 1, 1])

                with c_dist1:
                    # Protocolo Web Intent de LinkedIn para compartir en 1 clic
                    share_text = f"{ed_title}\n\n{ed_copy}"
                    encoded_text = urllib.parse.quote(share_text)
                    share_url = f"https://www.linkedin.com/feed/?shareActive=true&text={encoded_text}"
                    st.link_button("🌐 Abrir y Publicar en LinkedIn", share_url, use_container_width=True)

                with c_dist2:
                    # Descargar el texto en formato .txt limpio
                    contenido_descarga = f"TITULO: {ed_title}\n\n{ed_copy}\n\nIMAGEN ASOCIADA: banner-{msg_seleccionado.message_id}.png"
                    st.download_button(
                        label="📄 Descargar Copy (.txt)",
                        data=contenido_descarga,
                        file_name=f"linkedin-{msg_seleccionado.message_id}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )

                with c_dist3:
                    # Generar paquete ZIP en memoria con Texto + Imagen PNG
                    buf_zip = io.BytesIO()
                    with zipfile.ZipFile(buf_zip, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        zip_file.writestr(f"post_{msg_seleccionado.message_id}.txt", f"{ed_title}\n\n{ed_copy}")
                        if saved_img_path.exists():
                            zip_file.write(saved_img_path, arcname=f"banner_{msg_seleccionado.message_id}.png")

                    buf_zip.seek(0)
                    st.download_button(
                        label="📦 Descargar Media Kit (.zip)",
                        data=buf_zip,
                        file_name=f"media-kit-{msg_seleccionado.message_id}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

            # --- 4. ACCIÓN DE APROBACIÓN / DESCARTE ---
            if approved:
                st.session_state["approved_posts"][msg_seleccionado.message_id] = {
                    "post_id": f"POST-{msg_seleccionado.message_id[-6:]}",
                    "tipo": "LINKEDIN",
                    "title": ed_title,
                    "copy": ed_copy,
                    "author": msg_seleccionado.author_anon,
                    "origin_msg_id": msg_seleccionado.message_id,
                    "score": msg_seleccionado.opportunity_score,
                    "status": "APPROVED_FOR_OCI",
                    "imagen_path": str(saved_img_path) if saved_img_path.exists() else None
                }
                st.toast(f"✅ Post para {msg_seleccionado.message_id} aprobado.", icon="🎉")

            if rejected:
                if msg_seleccionado.message_id in st.session_state["approved_posts"]:
                    del st.session_state["approved_posts"][msg_seleccionado.message_id]
                st.toast(f"🚫 Activo {msg_seleccionado.message_id} descartado.", icon="⚠️")
        else:
            st.info("No se generó borrador de LinkedIn para esta interacción.")


# 2. PESTAÑA NEWSLETTER (BOLETÍN SEMANAL)
    with tab_newsletter:
        with st.container(border=True):
            st.markdown("##### 📰 Destaque para el Boletín Semanal de la Comunidad")
            titular_def = assets.destaque_newsletter_semanal.titular if assets.destaque_newsletter_semanal else f"Logro destacado: {msg_seleccionado.author_anon}"
            resumen_def = assets.destaque_newsletter_semanal.resumen if assets.destaque_newsletter_semanal else msg_seleccionado.clean_text[:140]

            news_titular = st.text_input("Titular de la Newsletter", value=titular_def, key=f"n_t_{msg_seleccionado.message_id}")
            news_resumen = st.text_area("Cuerpo / Resumen Informativo", value=resumen_def, height=130, key=f"n_r_{msg_seleccionado.message_id}")

            # --- BLOQUE MULTIMEDIA: HEADER PANORÁMICO (1200x400) ---
            img_key_news = f"img_{msg_seleccionado.message_id}_news"
            img_dir_news = Path("data/processed/generated/images")
            img_dir_news.mkdir(parents=True, exist_ok=True)
            saved_news_img_path = img_dir_news / f"news-{msg_seleccionado.message_id}.png"

            with st.container(border=True):
                st.markdown("##### 🎨 Header Panorámico para Newsletter (Pollinations AI - Flux)")
                c_n1, c_n2 = st.columns([1.2, 1.8])
                
                with c_n1:
                    prompt_sug_news = f"Wide panoramic modern tech newsletter header, abstract cloud network topology, warm orange and violet gradient, minimalist 3D studio render"
                    prompt_news_input = st.text_area("Prompt para Banner Panorámico:", value=prompt_sug_news, height=90, key=f"p_news_{msg_seleccionado.message_id}")
                    
                    if st.button("🖼️ Generar Header (1200x400)", key=f"b_news_{msg_seleccionado.message_id}", use_container_width=True):
                        with st.spinner("Generando banner panorámico con Flux..."):
                            try:
                                img_bytes, ext = generar(prompt_news_input, formato="destaque_newsletter")
                                st.session_state[img_key_news] = img_bytes
                                with open(saved_news_img_path, "wb") as f:
                                    f.write(img_bytes)
                                st.success(f"Header guardado: `{saved_news_img_path.name}`")
                            except Exception as e:
                                st.error(f"Error generando header: {e}")

                with c_n2:
                    if saved_news_img_path.exists() and img_key_news not in st.session_state:
                        with open(saved_news_img_path, "rb") as f:
                            st.session_state[img_key_news] = f.read()

                    if img_key_news in st.session_state:
                        st.image(st.session_state[img_key_news], caption="Header panorámico (1200x400)", use_container_width=True)
                        st.download_button(
                            label="💾 Descargar Banner PNG",
                            data=st.session_state[img_key_news],
                            file_name=f"header-news-{msg_seleccionado.message_id}.png",
                            mime="image/png",
                            use_container_width=True
                        )
                    else:
                        st.info("Presiona 'Generar Header' para crear la ilustración 1200x400.")

            # --- HERRAMIENTAS DE DISTRIBUCIÓN INMEDIATA (NEWSLETTER) ---
            with st.container(border=True):
                st.markdown("##### 🚀 Distribución Lista para Publicar")
                c_n_down1, c_n_down2, c_n_down3 = st.columns([1.3, 1, 1])
                
                with c_n_down1:
                    # Módulo HTML listo para Mailchimp, Substack o HubSpot
                    plantilla_html = f"""<div style="font-family: Arial, sans-serif; border-left: 4px solid #4F46E5; padding: 18px; background-color: #F8FAFC; border-radius: 8px;">
    <h3 style="color: #1E293B; margin-top: 0; font-size: 18px;">{news_titular}</h3>
    <p style="color: #475569; font-size: 14px; line-height: 1.6;">{news_resumen}</p>
    <div style="font-size: 12px; color: #64748B; margin-top: 10px;">
        <strong>Comunidad ONE &bull; Caso de Exito:</strong> {msg_seleccionado.author_anon}
    </div>
</div>"""
                    st.download_button(
                        label="📄 Descargar HTML para Correo",
                        data=plantilla_html,
                        file_name=f"newsletter-{msg_seleccionado.message_id}.html",
                        mime="text/html",
                        use_container_width=True
                    )

                with c_n_down2:
                    formato_md = f"### {news_titular}\n\n{news_resumen}\n\n*Fuente: Comunidad ONE • Estudiante {msg_seleccionado.author_anon}*"
                    st.download_button(
                        label="📝 Descargar Markdown (.md)",
                        data=formato_md,
                        file_name=f"newsletter-{msg_seleccionado.message_id}.md",
                        mime="text/markdown",
                        use_container_width=True
                    )

                with c_n_down3:
                    buf_news_zip = io.BytesIO()
                    with zipfile.ZipFile(buf_news_zip, "w", zipfile.ZIP_DEFLATED) as zip_f:
                        zip_f.writestr(f"newsletter_{msg_seleccionado.message_id}.html", plantilla_html)
                        zip_f.writestr(f"newsletter_{msg_seleccionado.message_id}.md", formato_md)
                        if saved_news_img_path.exists():
                            zip_f.write(saved_news_img_path, arcname=f"header_news_{msg_seleccionado.message_id}.png")

                    buf_news_zip.seek(0)
                    st.download_button(
                        label="📦 Descargar Kit Newsletter (.zip)",
                        data=buf_news_zip,
                        file_name=f"kit-newsletter-{msg_seleccionado.message_id}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✅ Aprobar para Newsletter Oficial (OCI)", key=f"btn_n_app_{msg_seleccionado.message_id}", type="primary", use_container_width=True):
                st.session_state["approved_posts"][f"NEWS-{msg_seleccionado.message_id}"] = {
                    "post_id": f"NEWS-{msg_seleccionado.message_id[-6:]}",
                    "tipo": "NEWSLETTER",
                    "title": news_titular,
                    "copy": news_resumen,
                    "author": msg_seleccionado.author_anon,
                    "origin_msg_id": msg_seleccionado.message_id,
                    "score": msg_seleccionado.opportunity_score,
                    "status": "APPROVED_FOR_OCI",
                    "imagen_path": str(saved_news_img_path) if saved_news_img_path.exists() else None
                }
                st.toast(f"✅ Newsletter aprobada para {msg_seleccionado.message_id}.", icon="📰")

    # 3. PESTAÑA FAQ (BASE DE CONOCIMIENTO Y MENTORÍAS)
    with tab_faq:
        with st.container(border=True):
            st.markdown("##### 💡 Base de Conocimiento y Guía de Mentoría Técnica")
            tema_faq = f"Tip Rápido sobre #{msg_seleccionado.channel}: {msg_seleccionado.clean_text[:50]}..."
            ed_faq_tema = st.text_input("Tema / Título de la FAQ", value=tema_faq, key=f"faq_t_{msg_seleccionado.message_id}")
            ed_faq_detalle = st.text_area("Detalle Técnico / Consulta de la Comunidad", value=msg_seleccionado.clean_text, height=130, key=f"faq_d_{msg_seleccionado.message_id}")

            # --- BLOQUE MULTIMEDIA: ILUSTRACIÓN TÉCNICA CUADRADA (1080x1080) ---
            img_key_faq = f"img_{msg_seleccionado.message_id}_faq"
            img_dir_faq = Path("data/processed/generated/images")
            img_dir_faq.mkdir(parents=True, exist_ok=True)
            saved_faq_img_path = img_dir_faq / f"faq-{msg_seleccionado.message_id}.png"

            with st.container(border=True):
                st.markdown("##### 🎨 Tarjeta Técnica / Carrusel Cuadrado (Pollinations AI - Flux)")
                c_f1, c_f2 = st.columns([1.2, 1.8])
                
                with c_f1:
                    prompt_sug_faq = f"Minimalist 3D isometric cloud infrastructure diagram, floating database nodes, clean dark background, tech tutorial concept"
                    prompt_faq_input = st.text_area("Prompt para Tarjeta Técnica (1080x1080):", value=prompt_sug_faq, height=90, key=f"p_faq_{msg_seleccionado.message_id}")
                    
                    if st.button("🖼️ Generar Tarjeta FAQ (1080x1080)", key=f"b_faq_{msg_seleccionado.message_id}", use_container_width=True):
                        with st.spinner("Generando tarjeta cuadrada con Flux..."):
                            try:
                                img_bytes, ext = generar(prompt_faq_input, formato="sugerencia_faq")
                                st.session_state[img_key_faq] = img_bytes
                                with open(saved_faq_img_path, "wb") as f:
                                    f.write(img_bytes)
                                st.success(f"Tarjeta técnica guardada: `{saved_faq_img_path.name}`")
                            except Exception as e:
                                st.error(f"Error generando tarjeta técnica: {e}")

                with c_f2:
                    if saved_faq_img_path.exists() and img_key_faq not in st.session_state:
                        with open(saved_faq_img_path, "rb") as f:
                            st.session_state[img_key_faq] = f.read()

                    if img_key_faq in st.session_state:
                        st.image(st.session_state[img_key_faq], caption="Tarjeta técnica 1080x1080", use_container_width=True)
                        st.download_button(
                            label="💾 Descargar Tarjeta PNG",
                            data=st.session_state[img_key_faq],
                            file_name=f"faq-card-{msg_seleccionado.message_id}.png",
                            mime="image/png",
                            use_container_width=True
                        )
                    else:
                        st.info("Presiona 'Generar Tarjeta FAQ' para crear la ilustración cuadrada 1080x1080.")

            # --- HERRAMIENTAS DE DISTRIBUCIÓN INMEDIATA (FAQ / DOCS) ---
            with st.container(border=True):
                st.markdown("##### 🚀 Distribución y Exportación de Documentación")
                c_faq_down1, c_faq_down2 = st.columns(2)
                
                faq_doc_md = f"""# 📘 FAQ Técnica: {ed_faq_tema}

> **Canal de Origen:** `#{msg_seleccionado.channel}`  
> **Planteado por:** {msg_seleccionado.author_anon}  
> **Fecha de Ingesta:** {msg_seleccionado.processed_at.strftime('%Y-%m-%d') if msg_seleccionado.processed_at else 'Reciente'}  

---

### ❓ Consulta de la Comunidad
{ed_faq_detalle}

---

### 💡 Guía / Respuesta Recomendada para Mentoría
*(Espacio reservado para notas de mentores e instructores de Oracle Cloud & Alura)*
"""
                with c_faq_down1:
                    st.download_button(
                        label="📚 Descargar Documentación FAQ (.md)",
                        data=faq_doc_md,
                        file_name=f"faq-{msg_seleccionado.message_id}.md",
                        mime="text/markdown",
                        use_container_width=True
                    )

                with c_faq_down2:
                    buf_faq_zip = io.BytesIO()
                    with zipfile.ZipFile(buf_faq_zip, "w", zipfile.ZIP_DEFLATED) as zip_f:
                        zip_f.writestr(f"faq_{msg_seleccionado.message_id}.md", faq_doc_md)
                        if saved_faq_img_path.exists():
                            zip_f.write(saved_faq_img_path, arcname=f"faq_card_{msg_seleccionado.message_id}.png")

                    buf_faq_zip.seek(0)
                    st.download_button(
                        label="📦 Descargar Paquete Doc + Imagen (.zip)",
                        data=buf_faq_zip,
                        file_name=f"paquete-faq-{msg_seleccionado.message_id}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✅ Aprobar como FAQ Oficial (OCI)", key=f"btn_faq_app_{msg_seleccionado.message_id}", type="primary", use_container_width=True):
                st.session_state["approved_posts"][f"FAQ-{msg_seleccionado.message_id}"] = {
                    "post_id": f"FAQ-{msg_seleccionado.message_id[-6:]}",
                    "tipo": "FAQ_EDUCATIVA",
                    "title": ed_faq_tema,
                    "copy": ed_faq_detalle,
                    "author": msg_seleccionado.author_anon,
                    "origin_msg_id": msg_seleccionado.message_id,
                    "score": msg_seleccionado.opportunity_score,
                    "status": "APPROVED_FOR_OCI",
                    "imagen_path": str(saved_faq_img_path) if saved_faq_img_path.exists() else None
                }
                st.toast(f"✅ FAQ guardada para {msg_seleccionado.message_id}.", icon="📚")