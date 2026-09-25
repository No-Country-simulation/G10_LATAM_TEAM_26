"""
CommunityLab AI - Vista: Persistencia & OCI
"""
import json
from pathlib import Path
import streamlit as st
from src.adapters.cloud.oci_storage import ObjectStorageAdapter
from src.domain.schemas import BatchInputPayload


def render_oci_view(dataset: BatchInputPayload | None):
    st.markdown('<div class="saas-title">Trazabilidad & Oracle Cloud Infrastructure</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Persistencia inmutable de activos en OCI Object Storage (capa Always Free).</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1.2, 1], gap="large")
    with c1:
        with st.container(border=True):
            st.markdown("##### 📍 Lineage de Datos (Trazabilidad Extremo a Extremo)")
            approved = st.session_state.get("approved_posts", {})
            if not approved:
                st.info("Aún no has aprobado ningún activo en el Content Studio. Aprueba al menos uno para sincronizar.")
            else:
                st.markdown(f"Total de activos aprobados: **{len(approved)}**")
                for k, item in approved.items():
                    st.code(f"""{item['post_id']} ({item.get('tipo', 'LINKEDIN')})
 └──► OPP ({item['status']} • Score {item['score']:.2f})
       └──► {item['origin_msg_id']} ({item['author']})""", language="text")

    with c2:
        with st.container(border=True):
            st.markdown("##### ☁️ Destino OCI Object Storage (Always Free)")
            st.markdown("**Bucket:** `communitylab-bucket`")
            st.markdown("**Namespace:** `oracle-one-latam-g10`")
            st.caption("Ruta configurada: `generated/linkedin/2026-semana-04/`")

            if approved:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🚀 Sincronizar Paquete Consolidado", type="primary", use_container_width=True):
                    storage = ObjectStorageAdapter()
                    first_item = list(approved.values())[0]

                    payload = {
                        "status": "exito",
                        "resumen_comunidad": {
                            "total_interacciones_procesadas": len(st.session_state.get("processed_results", [])),
                            "sentimiento_predominante": "Altamente Positivo",
                            "temas_principales": ["Contratacion / Logros", "LangChain / OCI", "n8n / Automatización"]
                        },
                        "activos_distribucion_generados": {
                            "post_linkedin": {
                                "titulo": first_item["title"],
                                "copy": first_item["copy"],
                                "canal_recomendado": "LinkedIn Oficial",
                                "potencial_engagement": "Alto"
                            }
                        }
                    }

                    periodo = dataset.periodo_referencia if dataset else "Semana_04"
                    resultado = storage.persist_distribution_package(payload, periodo)
                    st.session_state["oci_result"] = resultado
                    st.session_state["oci_payload"] = payload
                    st.success("¡Paquete estructurado persistido!")

            if "oci_result" in st.session_state:
                st.json(st.session_state["oci_result"])
                
                # BOTÓN DE DESCARGA PARA EL JURADO (Requisito de demo)
                payload_json = json.dumps(st.session_state["oci_payload"], ensure_ascii=False, indent=2)
                st.download_button(
                    label="💾 Descargar Paquete de Distribución (JSON)",
                    data=payload_json,
                    file_name="paquete-distribucion-communitylab.json",
                    mime="application/json",
                    use_container_width=True
                )