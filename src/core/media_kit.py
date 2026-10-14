"""
CommunityLab AI - Media kit
Texto listo para publicar de cada activo y ZIP con los activos aprobados (texto e imagen, una carpeta por formato)
más el paquete completo en JSON. Lo usan el panel de Streamlit y la API web. Basado en el media kit de Álvaro.
"""
import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List

CARPETAS = {"post_linkedin": "linkedin", "destaque_newsletter": "newsletter", "sugerencia_faq": "faq"}


def texto_publicable(activo: Dict[str, Any]) -> str:
    c = activo["contenido"]
    if activo["formato"] == "post_linkedin":
        return f"{c['copy']}\n\n{' '.join(c.get('hashtags', []))}\n"
    if activo["formato"] == "destaque_newsletter":
        return f"[{c['seccion']}]\n{c['titular']}\n\n{c['resumen']}\n"
    return f"{c['tema']}\n\n{c['cuerpo']}\n"


def media_kit(paquete: Dict[str, Any], activos: List[Dict[str, Any]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_kit:
        for activo in activos:
            if activo["estado_curaduria"] != "aprobado":
                continue
            base = f"{CARPETAS[activo['formato']]}/{activo['activo_id']}"
            zip_kit.writestr(f"{base}.txt", texto_publicable(activo))
            imagen = activo.get("imagen") or {}
            if imagen.get("estado") == "lista" and imagen.get("ruta") and Path(imagen["ruta"]).exists():
                zip_kit.write(imagen["ruta"], f"{base}{Path(imagen['ruta']).suffix}")
        zip_kit.writestr(f"{paquete['paquete_id']}.json", json.dumps(paquete, ensure_ascii=False, indent=2))
    return buffer.getvalue()
