"""
CommunityLab AI - Vista: Persistencia & OCI
Guarda el paquete completo (Formato B) con los estados de curaduría del panel.
"""
import json

import streamlit as st

from src.adapters.cloud.oci_storage import ObjectStorageAdapter
from src.domain.schemas import BatchInputPayload


def render_oci_view(dataset: BatchInputPayload | None):
    st.markdown('<div class="saas-title">Trazabilidad & Oracle Cloud Infrastructure</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Persistencia del paquete de distribución en OCI Object Storage '
                '(capa Always Free).</div>', unsafe_allow_html=True)

    paquete = st.session_state.get("paquete")
    if not paquete:
        st.info("Todavía no hay un paquete. Procesa un lote en 'Detección & Scoring'.")
        return

    activos = paquete["activos"]
    aprobados = [a for a in activos if a["estado_curaduria"] == "aprobado"]
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
            st.markdown(f"**Bucket:** `{paquete['almacenamiento_oci']['bucket']}`")
            st.markdown(f"**Ruta:** `{paquete['almacenamiento_oci']['ruta_objeto']}`")
            st.markdown(f"**Paquete:** `{paquete['paquete_id']}` · estado `{paquete['status']}` · "
                        f"{len(aprobados)} de {len(activos)} activos aprobados")
            st.caption("Hoy se guarda en data/processed/ con la misma ruta; la subida al bucket real se conecta "
                       "en el adaptador de OCI sin cambiar esta vista.")

            generacion = st.session_state.get("generacion")
            redactando = generacion is not None and not generacion.terminado
            if redactando:
                st.warning(f"Todavía se están redactando borradores ({len(generacion.activos)} de "
                           f"{generacion.total_piezas}). Espera a que termine para guardar el paquete completo.")
            if st.button("🚀 Guardar paquete", type="primary", use_container_width=True, disabled=redactando):
                resultado = ObjectStorageAdapter().persist_distribution_package(paquete)
                paquete["almacenamiento_oci"]["status"] = resultado["status"]
                st.session_state["oci_result"] = resultado
                st.success("Paquete guardado.")

            if "oci_result" in st.session_state:
                st.json(st.session_state["oci_result"])

            st.download_button(
                label="💾 Descargar paquete de distribución (JSON)",
                data=json.dumps(paquete, ensure_ascii=False, indent=2),
                file_name=f"{paquete['paquete_id']}.json",
                mime="application/json",
                use_container_width=True,
            )
