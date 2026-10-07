"""
CommunityLab AI - Vista: Persistencia & OCI
Guarda el paquete completo (Formato B) con los estados de curaduría del panel: en OCI Object Storage (con sus
imágenes) si hay credenciales, siempre con copia local, y registra sus activos en la base de la comunidad.
"""
import json

import streamlit as st

from src.adapters.cloud.oci_storage import ObjectStorageAdapter
from src.adapters.db import repository
from src.domain.schemas import BatchInputPayload


@st.cache_resource
def _almacenamiento() -> ObjectStorageAdapter:
    return ObjectStorageAdapter()


def render_oci_view(dataset: BatchInputPayload | None):
    st.markdown('<div class="saas-title">Trazabilidad & Oracle Cloud Infrastructure</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Persistencia del paquete de distribución en OCI Object Storage '
                '(capa Always Free).</div>', unsafe_allow_html=True)

    paquete = st.session_state.get("paquete")
    if not paquete:
        st.info("Todavía no hay un paquete. Procesa un lote en 'Detección & Scoring'.")
        return

    almacenamiento = _almacenamiento()
    activos = paquete["activos"]
    aprobados = [a for a in activos if a["estado_curaduria"] == "aprobado"]
    con_imagen = [a for a in activos if (a.get("imagen") or {}).get("estado") == "lista"]
    c1, c2 = st.columns([1.2, 1], gap="large")
    with c1:
        with st.container(border=True):
            st.markdown("##### 📍 Trazabilidad de los activos aprobados")
            if not aprobados:
                st.info("Aún no aprobaste ningún activo en el Content Studio. El paquete se puede guardar igual: "
                        "todos los activos viajan con su estado de curaduría.")
            for a in aprobados:
                st.code(f"{a['activo_id']} ({a['formato']})\n"
                        f" └──► {a['origen']['opportunity_id']} ({a['origen']['type']} • Score {a['origen']['score']:.2f})\n"
                        f"       └──► {a['origen']['message_id']} (#{a['origen'].get('channel') or 'sin canal'})",
                        language="text")

    with c2:
        with st.container(border=True):
            st.markdown("##### ☁️ Destino OCI Object Storage (Always Free)")
            st.markdown(f"**Bucket:** `{almacenamiento.bucket_name}`"
                        + (f" · namespace `{almacenamiento.namespace}`" if almacenamiento.namespace else ""))
            st.markdown(f"**Ruta:** `{paquete['almacenamiento_oci']['ruta_objeto']}`")
            st.markdown(f"**Paquete:** `{paquete['paquete_id']}` · estado `{paquete['status']}` · "
                        f"{len(aprobados)} de {len(activos)} activos aprobados · {len(con_imagen)} con imagen")
            if almacenamiento.conectado:
                st.caption("✅ Conectado a OCI: el paquete y sus imágenes se suben al bucket (y queda copia local).")
            else:
                st.caption("Sin credenciales de OCI en el .env: el paquete se guarda en data/processed/ con la misma "
                           "ruta que tendrá en el bucket.")

            generacion = st.session_state.get("generacion")
            redactando = generacion is not None and not generacion.terminado
            if redactando:
                st.warning(f"Todavía se están redactando borradores ({len(generacion.activos)} de "
                           f"{generacion.total_piezas}). Espera a que termine para guardar el paquete completo.")
            if st.button("🚀 Guardar paquete", type="primary", use_container_width=True, disabled=redactando):
                with st.spinner("Guardando el paquete…"):
                    resultado = almacenamiento.persist_distribution_package(paquete)
                    if st.session_state.get("modo_simulado"):
                        resultado["activos_en_base"] = "no se registran (modo simulado)"
                    else:
                        try:
                            resultado["activos_en_base"] = repository.guardar_activos(
                                paquete, st.session_state.get("comunidad_lote", paquete["origen_comunidad"]),
                                st.session_state.get("username"))
                        except Exception as error:
                            resultado["activos_en_base"] = f"no se pudieron registrar ({type(error).__name__})"
                st.session_state["oci_result"] = resultado
                if resultado["status"] == "guardado_con_exito":
                    st.success(f"Paquete subido a OCI con {resultado['imagenes_subidas']} imágenes.")
                elif "error" in resultado:
                    st.warning("No se pudo subir a OCI; quedó la copia local.")
                else:
                    st.success("Paquete guardado en local.")

            if "oci_result" in st.session_state:
                st.json(st.session_state["oci_result"])

            st.download_button(
                label="💾 Descargar paquete de distribución (JSON)",
                data=json.dumps(paquete, ensure_ascii=False, indent=2),
                file_name=f"{paquete['paquete_id']}.json",
                mime="application/json",
                use_container_width=True,
            )
