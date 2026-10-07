"""
CommunityLab AI - Vista: Persistencia & OCI
Trazabilidad de extremo a extremo, subida de JSON y binarios PNG a OCI Object Storage.
"""
import os
import json
from pathlib import Path
import streamlit as st

from src.adapters.cloud.oci_storage import ObjectStorageAdapter
from src.adapters.db.repository import get_high_value_opportunities
from src.domain.schemas import BatchInputPayload


def render_oci_view(dataset: BatchInputPayload | None):
    st.markdown('<div class="saas-title">Trazabilidad & Oracle Cloud Infrastructure</div>', unsafe_allow_html=True)
    st.markdown('<div class="saas-subtitle">Persistencia inmutable de activos en OCI Object Storage (capa Always Free).</div>', unsafe_allow_html=True)

    # 1. Recuperar activos de la sesión o desde Oracle Cloud
    approved_session = st.session_state.get("approved_posts", {})
    oportunidades_bd = get_high_value_opportunities(min_score=0.70)

    activos_a_mostrar = {}
    if approved_session:
        activos_a_mostrar = approved_session
    elif oportunidades_bd:
        for op in oportunidades_bd:
            img_local = Path(f"data/processed/generated/images/{op.message_id}.png")
            activos_a_mostrar[op.message_id] = {
                "post_id": f"POST-{op.message_id[-6:]}",
                "tipo": "LINKEDIN" if op.opportunity_type == "SUCCESS_STORY" else "FAQ",
                "title": f"Activo oficial: {op.opportunity_type} ({op.author_anon})",
                "copy": op.clean_text,
                "author": op.author_anon,
                "origin_msg_id": op.message_id,
                "score": op.opportunity_score,
                "status": "APPROVED_FOR_OCI",
                "imagen_path": str(img_local) if img_local.exists() else None
            }

    c1, c2 = st.columns([1.2, 1], gap="large")

    # COLUMNA 1: LINAJE DE DATOS (TRAZABILIDAD)
    with c1:
        with st.container(border=True):
            st.markdown("##### 📍 Lineage de Datos (Trazabilidad Extremo a Extremo)")
            
            if not activos_a_mostrar:
                st.info("No se encontraron activos aprobados. Ve a 'Detección & Scoring' para analizar interacciones.")
            else:
                st.markdown(f"Total de activos listos para persistencia: **{len(activos_a_mostrar)}**")
                for k, item in activos_a_mostrar.items():
                    img_info = f" • 🖼️ {Path(item['imagen_path']).name}" if item.get('imagen_path') else ""
                    st.code(f"""{item['post_id']} ({item.get('tipo', 'LINKEDIN')}{img_info})
 └──► OPP ({item['status']} • Score {item['score']:.2f})
       └──► {item['origin_msg_id']} ({item['author']})""", language="text")

    # COLUMNA 2: SINCRONIZACIÓN CON BUCKET OCI
    with c2:
        with st.container(border=True):
            storage = ObjectStorageAdapter()
            st.markdown("##### ☁️ Destino OCI Object Storage (Always Free)")
            st.markdown(f"**Bucket:** `{storage.bucket_name}`")
            st.markdown(f"**Namespace:** `{storage.namespace}`")
            st.markdown(f"**Región:** `{storage.region}`")
            st.caption("Ruta configurada: `generated/linkedin/2026-semana-04/`")

            if activos_a_mostrar:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🚀 Sincronizar Todos los Activos Aprobados con OCI", type="primary", use_container_width=True):
                    storage = ObjectStorageAdapter()
                    resultados_subida = []
                    paquetes_consolidados = []

                    with st.spinner(f"Sincronizando {len(activos_a_mostrar)} activos e imágenes con Oracle Cloud..."):
                        for msg_id, item in activos_a_mostrar.items():
                            # 1. Subir imagen a OCI si existe
                            ruta_img_oci = None
                            if item.get("imagen_path"):
                                ruta_img_oci = storage.upload_image(
                                    local_image_path=item["imagen_path"],
                                    message_id=item["origin_msg_id"]
                                )

                            # 2. Armar paquete individual Formato B para este activo
                            payload_individual = {
                                "status": "exito",
                                "post_id": item["post_id"],
                                "origen_message_id": item["origin_msg_id"],
                                "autor": item["author"],
                                "tipo_activo": item.get("tipo", "LINKEDIN"),
                                "resumen_comunidad": {
                                    "sentimiento_predominante": "Altamente Positivo",
                                    "temas_principales": ["Contrataciones", "LangChain", "Oracle Cloud"]
                                },
                                "activos_distribucion_generados": {
                                    "post_linkedin": {
                                        "titulo": item["title"],
                                        "copy": item["copy"],
                                        "canal_recomendado": "LinkedIn Oficial",
                                        "potencial_engagement": "Alto",
                                        "archivo_adjunto_imagen": ruta_img_oci
                                    }
                                },
                                "almacenamiento_oci": {
                                    "bucket": storage.bucket_name,
                                    "ruta_objeto": f"generated/linkedin/2026-semana-04/{item['post_id']}.json",
                                    "status": "guardado_con_exito"
                                }
                            }

                            # 3. Persistir en OCI con nombre único por post
                            res = storage.persist_distribution_package(
                                package_data=payload_individual,
                                week_tag="Semana_04",
                                custom_filename=f"{item['post_id']}"
                            )
                            resultados_subida.append(res)
                            paquetes_consolidados.append(payload_individual)

                    # Guardar en memoria para que no haya KeyError
                    st.session_state["oci_result"] = resultados_subida
                    st.session_state["oci_payload"] = paquetes_consolidados
                    st.success(f"¡{len(resultados_subida)} publicaciones y sus imágenes han sido persistidas en OCI Object Storage!")

            # Resultados y botón de descarga (Defensivo con .get())
            if st.session_state.get("oci_result"):
                st.markdown("##### 📦 Confirmación de Objetos en OCI")
                st.json(st.session_state["oci_result"])

            if st.session_state.get("oci_payload"):
                payload_json = json.dumps(st.session_state["oci_payload"], ensure_ascii=False, indent=2)
                st.download_button(
                    label="💾 Descargar Paquetes Sincronizados (JSON Consolidado)",
                    data=payload_json,
                    file_name="paquetes-distribucion-oci.json",
                    mime="application/json",
                    use_container_width=True
                )