"""
CommunityLab AI - Unit Tests
Publicaciones guardadas en OCI: los dos formatos del bucket, sin repetidos y con su imagen.
"""
import json

from src.api.publicaciones import normalizar, ruta_de_imagen_valida

POST_ANTERIOR = {
    "post_id": "POST-896216", "origen_message_id": "DISC-896216", "autor": "Gregory",
    "activos_distribucion_generados": {"post_linkedin": {"titulo": "Primer trabajo", "copy": "¡Hoy empecé!",
                                                         "archivo_adjunto_imagen": None}},
}
PAQUETE = {
    "paquete_id": "PKG-1", "fecha_generacion": "2026-10-08T20:00:00Z",
    "activos": [{"activo_id": "FAQ-001", "formato": "sugerencia_faq", "estado_curaduria": "aprobado",
                 "origen": {"autor": "Luis A.", "message_id": "MSG-2", "type": "FAQ", "score": 0.8},
                 "contenido": {"tema": "¿Cómo uso OCI?", "cuerpo": "1. Entra a la consola"},
                 "imagen": {"estado": "lista", "ruta_oci": "generated/2026-10-08/img/PKG-1/FAQ-001.jpg"}}],
}


def test_normaliza_los_dos_formatos_sin_repetidos():
    objetos = [
        {"name": "generated/linkedin/2026-10-05/POST-896216.json", "time_created": "2026-10-05T22:30:00"},
        {"name": "generated/linkedin/2026-10-07/POST-896216.json", "time_created": "2026-10-07T00:16:00"},
        {"name": "generated/images/2026-10-07/DISC-896216.png", "time_created": "2026-10-07T00:16:00"},
        {"name": "generated/2026-10-08/PKG-1.json", "time_created": "2026-10-08T20:00:05"},
        {"name": "generated/roto.json", "time_created": "2026-10-01T00:00:00"},
    ]
    contenido = {objetos[0]["name"]: POST_ANTERIOR, objetos[1]["name"]: POST_ANTERIOR, objetos[3]["name"]: PAQUETE}

    def leer(nombre):
        if nombre not in contenido:
            return b"no es json"
        return json.dumps(contenido[nombre]).encode()

    items = normalizar(objetos, leer)
    assert [i["titulo"] for i in items] == ["¿Cómo uso OCI?", "Primer trabajo"]  # más reciente primero
    faq, post = items
    assert faq["formato"] == "sugerencia_faq" and faq["imagen"].endswith("FAQ-001.jpg") and faq["veces_guardado"] == 1
    assert post["veces_guardado"] == 2 and post["fecha"].startswith("2026-10-07")
    assert post["imagen"] == "generated/images/2026-10-07/DISC-896216.png"  # la imagen se encuentra por el mensaje


def test_solo_sirve_imagenes_del_prefijo_generated():
    assert ruta_de_imagen_valida("generated/images/2026-10-07/DISC-1.png")
    assert not ruta_de_imagen_valida("generated/../secreto.png")
    assert not ruta_de_imagen_valida("otra/carpeta/x.png")
    assert not ruta_de_imagen_valida("generated/paquete.json")
