"""
CommunityLab AI - Vista: Content Studio (Curaduría Multiformato)
Edita y aprueba los activos del paquete (Formato B). El panel es el único módulo que cambia
estado_curaduria: borrador -> aprobado | descartado; editar un aprobado lo devuelve a borrador.
"""
import io
import json
import zipfile
from pathlib import Path

import streamlit as st

from src.core.agents.strategist import regenerar_pieza
from src.core.orchestrator import generar_imagenes
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


def _texto_publicable(activo: dict) -> str:
    c = activo["contenido"]
    if activo["formato"] == "post_linkedin":
        return f"{c['copy']}\n\n{' '.join(c.get('hashtags', []))}\n"
    if activo["formato"] == "destaque_newsletter":
        return f"[{c['seccion']}]\n{c['titular']}\n\n{c['resumen']}\n"
    return f"{c['tema']}\n\n{c['cuerpo']}\n"


def media_kit(paquete: dict, activos: list) -> bytes:
    """ZIP con los activos aprobados listos para publicar (texto e imagen, una carpeta por formato) y el paquete
    completo en JSON. Basado en el media kit de Álvaro."""
    carpetas = {"post_linkedin": "linkedin", "destaque_newsletter": "newsletter", "sugerencia_faq": "faq"}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_kit:
        for activo in activos:
            if activo["estado_curaduria"] != "aprobado":
                continue
            base = f"{carpetas[activo['formato']]}/{activo['activo_id']}"
            zip_kit.writestr(f"{base}.txt", _texto_publicable(activo))
            imagen = activo.get("imagen") or {}
            if imagen.get("estado") == "lista" and imagen.get("ruta") and Path(imagen["ruta"]).exists():
                zip_kit.write(imagen["ruta"], f"{base}{Path(imagen['ruta']).suffix}")
        zip_kit.writestr(f"{paquete['paquete_id']}.json", json.dumps(paquete, ensure_ascii=False, indent=2))
    return buffer.getvalue()


TEXTOS_IMAGEN = {
    "pendiente": "⏳ En cola: se genera en segundo plano, de mayor a menor score.",
    "generando": "🎨 Generando la imagen…",
    "omitida": "Se alcanzó el máximo de imágenes por paquete (IMAGENES_MAX).",
}


def _relanzar_imagenes(paquete: dict) -> None:
    """Si el hilo de imágenes ya terminó, arranca otro para las que quedaron pendientes (p. ej. un reintento)."""
    hilo = st.session_state.get("hilo_imagenes")
    if not hilo or hilo.terminado:
        st.session_state["hilo_imagenes"] = generar_imagenes(paquete)


@st.fragment(run_every=3)
def imagen_del_activo(activo: dict, paquete: dict, prefijo: str):
    """Imagen de la publicación: se refresca sola mientras está en cola o generándose."""
    imagen = activo.get("imagen")
    st.markdown("##### 🖼️ Imagen de la publicación")
    if not imagen:
        st.caption("Sin imagen (modo simulado, línea de comandos o imágenes desactivadas con LLM_IMAGENES=0).")
        return
    estado = imagen.get("estado")
    if estado == "lista" and imagen.get("ruta"):
        st.image(imagen["ruta"], use_container_width=True)
        with open(imagen["ruta"], "rb") as archivo:
            st.download_button("⬇️ Descargar imagen", archivo.read(), file_name=Path(imagen["ruta"]).name,
                               key=f"{prefijo}_img_descargar")
    elif estado == "error":
        st.warning(f"No se pudo generar la imagen ({imagen.get('detalle', 'error')}).")
    else:
        st.info(TEXTOS_IMAGEN.get(estado, estado))
    st.caption(f"Prompt: {imagen.get('prompt', '')}")
    if estado in ("lista", "error", "omitida") and st.button("🔄 Generar otra imagen", key=f"{prefijo}_img_otra"):
        imagen.update(estado="pendiente", ruta=None, intentos=0)
        _relanzar_imagenes(paquete)
        st.rerun(scope="fragment")


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

    if conteo["aprobado"]:
        st.download_button(f"📦 Descargar media kit ({conteo['aprobado']} aprobados, ZIP)",
                           media_kit(paquete, activos), file_name=f"{paquete['paquete_id']}_media_kit.zip",
                           mime="application/zip", key=f"{paquete['paquete_id']}_media_kit")

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

    with st.container(border=True):
        imagen_del_activo(activo, paquete, prefijo)

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
