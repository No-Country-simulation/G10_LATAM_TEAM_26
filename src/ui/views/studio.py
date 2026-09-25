"""
CommunityLab AI - Vista: Content Studio (Curaduría Multiformato)
Edita y aprueba los activos del paquete (Formato B). El panel es el único módulo que cambia
estado_curaduria: borrador -> aprobado | descartado; editar un aprobado lo devuelve a borrador.
"""
import streamlit as st

from src.core.agents.strategist import regenerar_pieza
from src.ui.components.post_editor import render_linkedin_editor

ETIQUETAS = {"post_linkedin": "📱 Post LinkedIn", "destaque_newsletter": "📰 Newsletter", "sugerencia_faq": "💡 FAQ"}
ICONOS_ESTADO = {"borrador": "📝", "aprobado": "✅", "descartado": "🚫", "publicado": "🚀"}


def _claves_widget(prefijo: str) -> list:
    return [k for k in st.session_state if isinstance(k, str) and k.startswith(prefijo)]


def _guardar(activo: dict, contenido: dict, estado: str) -> None:
    activo["contenido"].update(contenido)
    activo["estado_curaduria"] = estado


def _editado(activo: dict, contenido: dict) -> bool:
    return any(activo["contenido"].get(k) != v for k, v in contenido.items())


@st.fragment(run_every=2)
def progreso_studio(mostrados: int):
    """Avisa cuántos borradores llegaron desde el último dibujo, sin recargar lo que el curador edita."""
    generacion = st.session_state.get("generacion")
    if not generacion:
        return
    listos = len(generacion.activos)
    if mostrados == 0 and listos > 0:
        st.rerun(scope="app")  # todavía no hay nada que editar: se puede mostrar la lista de inmediato
    texto = f"✍️ Redactando borradores: {listos} de {generacion.total_piezas} listos."
    if generacion.terminado:
        texto = f"✅ Redacción terminada: {listos} de {generacion.total_piezas} borradores."
    c_texto, c_boton = st.columns([3, 1])
    c_texto.info(texto)
    nuevos = listos - mostrados
    if nuevos > 0 and c_boton.button(f"🔄 Mostrar {nuevos} nuevos", use_container_width=True):
        st.rerun(scope="app")


def render_studio_view():
    st.markdown('<div class="saas-title">Content Studio — Human-in-the-Loop</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Supervisión, ajuste editorial multiformato y aprobación previa a OCI.</div>',
                unsafe_allow_html=True)

    paquete = st.session_state.get("paquete")
    generacion = st.session_state.get("generacion")
    # Copia de la lista: el hilo de redacción puede agregar borradores mientras se dibuja la página
    activos = list(paquete["activos"]) if paquete else []
    if generacion and not generacion.terminado:
        progreso_studio(len(activos))
    if not activos:
        if generacion and not generacion.terminado:
            st.info("Los primeros borradores aparecerán aquí en unos segundos.")
        else:
            st.warning("No hay borradores listos. Ve a 'Detección & Scoring' y ejecuta el análisis primero.")
        return

    conteo = {e: sum(1 for a in activos if a["estado_curaduria"] == e) for e in ("borrador", "aprobado", "descartado")}
    st.success(f"**{len(activos)}** borradores en el paquete · 📝 {conteo['borrador']} por revisar · "
               f"✅ {conteo['aprobado']} aprobados · 🚫 {conteo['descartado']} descartados")

    por_id = {a["activo_id"]: a for a in activos}
    elegido = st.selectbox(
        "Selecciona un borrador para revisar:", list(por_id),
        format_func=lambda i: f"{ICONOS_ESTADO[por_id[i]['estado_curaduria']]} {i} · {ETIQUETAS[por_id[i]['formato']]} · "
                              f"{por_id[i]['origen']['type']} {por_id[i]['origen']['score']:.2f}")
    activo = por_id[elegido]
    origen = activo["origen"]
    prefijo = f"{paquete['paquete_id']}_{activo['activo_id']}"

    with st.container(border=True):
        st.markdown(f"**Mensaje original** · `{origen['message_id']}` · `#{origen.get('channel') or 'sin canal'}` · "
                    f"{origen['type']} **{origen['score']:.2f}**")
        st.markdown(f"> {origen['message']}")
        st.caption(f"🧠 {origen['reason']}")

    with st.expander("✨ Ajustar o regenerar con IA (indicaciones del curador)", expanded=False):
        c_inst, c_btn = st.columns([3, 1])
        with c_inst:
            indicaciones = st.text_input(
                "Indicación para la IA:",
                placeholder="Ej: 'Hazlo más breve', 'Enfócate en el cambio de carrera', 'Cierra con una pregunta'...",
                key=f"{prefijo}_indicaciones")
        with c_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Regenerar", use_container_width=True, key=f"{prefijo}_regenerar"):
                with st.spinner("La IA está reescribiendo el borrador..."):
                    nuevo = regenerar_pieza(activo, indicaciones, st.session_state.get("modo_simulado", False))
                if nuevo:
                    _guardar(activo, nuevo, "borrador")
                    for k in _claves_widget(prefijo):  # los campos deben mostrar el texto nuevo
                        if not k.endswith("_indicaciones"):
                            del st.session_state[k]
                    st.rerun()
                else:
                    st.error("No se pudo regenerar el borrador (revisa la cuota de la IA).")

    contenido = activo["contenido"]
    if activo["formato"] == "post_linkedin":
        aprobar, descartar, titulo, copy = render_linkedin_editor(
            msg_id=prefijo, author=origen.get("autor") or "Miembro",
            default_title=contenido["titulo"], default_copy=contenido["copy"])
        tags = st.text_input("Hashtags", value=" ".join(contenido["hashtags"]), key=f"{prefijo}_hashtags")
        editado = {"titulo": titulo, "copy": copy, "hashtags": [t for t in tags.split() if t]}
    else:
        with st.container(border=True):
            if activo["formato"] == "destaque_newsletter":
                st.markdown("##### 📰 Destaque para el boletín semanal")
                seccion = st.text_input("Sección", value=contenido["seccion"], key=f"{prefijo}_seccion")
                titular = st.text_input("Titular", value=contenido["titular"], key=f"{prefijo}_titular")
                resumen = st.text_area("Resumen", value=contenido["resumen"], height=120, key=f"{prefijo}_resumen")
                editado = {"seccion": seccion, "titular": titular, "resumen": resumen}
            else:
                st.markdown("##### 💡 Entrada para la base de preguntas frecuentes")
                tema = st.text_input("Pregunta / tema", value=contenido["tema"], key=f"{prefijo}_tema")
                cuerpo = st.text_area("Respuesta", value=contenido["cuerpo"], height=180, key=f"{prefijo}_cuerpo")
                st.caption(f"Origen: {contenido.get('origen_descripcion', '')}")
                editado = {"tema": tema, "cuerpo": cuerpo}
            c_a, c_b = st.columns(2)
            aprobar = c_a.button("✅ Aprobar", key=f"{prefijo}_aprobar", type="primary", use_container_width=True)
            descartar = c_b.button("🚫 Descartar", key=f"{prefijo}_descartar", use_container_width=True)

    if aprobar:
        _guardar(activo, editado, "aprobado")
        st.toast(f"✅ {activo['activo_id']} aprobado.", icon="🎉")
        st.rerun()
    elif descartar:
        _guardar(activo, editado, "descartado")
        st.toast(f"🚫 {activo['activo_id']} descartado.", icon="⚠️")
        st.rerun()
    elif _editado(activo, editado):
        # Las ediciones se guardan al momento: Streamlit olvida los campos al cambiar de borrador
        volvio_a_revision = activo["estado_curaduria"] == "aprobado"
        _guardar(activo, editado, "borrador" if volvio_a_revision else activo["estado_curaduria"])
        if volvio_a_revision:
            st.info("Editaste un activo aprobado: vuelve a borrador hasta que lo apruebes de nuevo.")
