"""
CommunityLab AI - Publicaciones guardadas en OCI Object Storage
Lee lo que quedó en el bucket (prefijo generated/) y lo normaliza a una lista de publicaciones para el front.
Entiende los dos formatos que conviven en el bucket:
  - paquetes del Formato B (spec.md): generated/YYYY-MM-DD/<paquete_id>.json, con sus activos e imágenes;
  - publicaciones de la versión de Álvaro: generated/linkedin/<fecha>/POST-*.json y paquete-*.json, con
    'activos_distribucion_generados' y la imagen en generated/images/<fecha>/<mensaje>.png.
La misma publicación guardada varias veces aparece una sola vez (la más reciente), con cuántas veces se guardó.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional

PREFIJO = "generated/"
EXTENSIONES_IMAGEN = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
FORMATOS = {"post_linkedin": "post_linkedin", "destaque_newsletter": "destaque_newsletter",
            "destaque_newsletter_semanal": "destaque_newsletter", "sugerencia_faq": "sugerencia_faq",
            "faq": "sugerencia_faq"}


def _texto(contenido: Dict[str, Any]) -> tuple:
    titulo = contenido.get("titulo") or contenido.get("titular") or contenido.get("tema") or ""
    cuerpo = contenido.get("copy") or contenido.get("resumen") or contenido.get("cuerpo") or ""
    return titulo, cuerpo


def _de_paquete(nombre: str, fecha: str, datos: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Activos de un paquete del Formato B."""
    items = []
    for activo in datos.get("activos", []):
        titulo, cuerpo = _texto(activo.get("contenido", {}))
        origen = activo.get("origen", {})
        imagen = (activo.get("imagen") or {}).get("ruta_oci")
        items.append({
            "id": f"{datos.get('paquete_id')}/{activo.get('activo_id')}", "formato": activo.get("formato"),
            "titulo": titulo, "texto": cuerpo, "hashtags": activo.get("contenido", {}).get("hashtags", []),
            "estado": activo.get("estado_curaduria"), "autor": origen.get("autor"), "canal": origen.get("channel"),
            "mensaje_id": origen.get("message_id"), "tipo": origen.get("type"), "score": origen.get("score"),
            "imagen": imagen, "fecha": datos.get("fecha_generacion") or fecha, "objeto": nombre,
            "paquete": datos.get("paquete_id"), "origen_formato": "paquete",
        })
    return items


def _de_version_anterior(nombre: str, fecha: str, datos: Dict[str, Any], imagenes: Dict[str, str]) -> List[Dict[str, Any]]:
    """Publicaciones guardadas por la versión de Álvaro (un JSON por publicación o por paquete)."""
    items = []
    mensaje = datos.get("origen_message_id")
    for clave, contenido in (datos.get("activos_distribucion_generados") or {}).items():
        if not isinstance(contenido, dict):
            continue
        titulo, cuerpo = _texto(contenido)
        imagen = contenido.get("archivo_adjunto_imagen") or (imagenes.get(mensaje) if mensaje else None)
        items.append({
            "id": f"{datos.get('post_id') or PurePosixPath(nombre).stem}/{clave}",
            "formato": FORMATOS.get(clave, clave), "titulo": titulo, "texto": cuerpo,
            "hashtags": contenido.get("hashtags", []), "estado": "aprobado", "autor": datos.get("autor"),
            "canal": None, "mensaje_id": mensaje, "tipo": None, "score": None, "imagen": imagen,
            "fecha": fecha, "objeto": nombre, "paquete": None, "origen_formato": "version_anterior",
        })
    return items


def normalizar(objetos: List[Dict[str, Any]], leer) -> List[Dict[str, Any]]:
    """objetos: [{name, time_created}] del bucket. leer(name) -> bytes. Devuelve las publicaciones, más recientes
    primero, sin repetidos."""
    imagenes = {PurePosixPath(o["name"]).stem: o["name"] for o in objetos
                if PurePosixPath(o["name"]).suffix.lower() in EXTENSIONES_IMAGEN}
    jsons = [o for o in objetos if o["name"].endswith(".json")]

    def procesar(o):
        try:
            datos = json.loads(leer(o["name"]))
        except Exception:
            return []
        if "activos" in datos and "paquete_id" in datos:
            return _de_paquete(o["name"], o["time_created"], datos)
        return _de_version_anterior(o["name"], o["time_created"], datos, imagenes)

    with ThreadPoolExecutor(max_workers=8) as hilos:
        todos = [item for lista in hilos.map(procesar, jsons) for item in lista]

    unicos: Dict[tuple, Dict[str, Any]] = {}
    for item in sorted(todos, key=lambda i: str(i["fecha"])):
        clave = (item["id"], item["titulo"], item["texto"])
        veces = unicos[clave]["veces_guardado"] + 1 if clave in unicos else 1
        unicos[clave] = {**item, "veces_guardado": veces}
    return sorted(unicos.values(), key=lambda i: str(i["fecha"]), reverse=True)


def ruta_de_imagen_valida(ruta: Optional[str]) -> bool:
    return bool(ruta) and ruta.startswith(PREFIJO) and ".." not in ruta \
        and PurePosixPath(ruta).suffix.lower() in EXTENSIONES_IMAGEN
