"""
CommunityLab AI - Adaptador de generación de imágenes (Pollinations.ai)
Una imagen a partir de un prompt en inglés. Se usa según la documentación oficial del servicio: sin cuenta respeta
el límite de 1 imagen cada 15 s; con POLLINATIONS_TOKEN (registro gratuito) puede pedir sin marca de agua.
Las imágenes se piden como privadas para que no aparezcan en la galería pública del servicio.
"""
from typing import Tuple
from urllib.parse import quote

import requests

from src import config

URL = "https://image.pollinations.ai/prompt/"
TAMANOS = {"post_linkedin": (1200, 627), "sugerencia_faq": (1080, 1080), "destaque_newsletter": (1200, 400)}
ESTILO = "3D illustration, soft studio lighting, clean background. No people, no text, no letters, no words."


def generar(prompt: str, formato: str, semilla: int = 0) -> Tuple[bytes, str]:
    """Devuelve (bytes, extensión). Lanza una excepción si el servicio no devuelve una imagen."""
    ancho, alto = TAMANOS.get(formato, (1024, 1024))
    parametros = {"width": ancho, "height": alto, "model": "flux", "private": "true", "seed": semilla}
    cabeceras = {}
    if config.POLLINATIONS_TOKEN:
        cabeceras["Authorization"] = f"Bearer {config.POLLINATIONS_TOKEN}"
        parametros["nologo"] = "true"
    respuesta = requests.get(URL + quote(f"{prompt.strip().rstrip('.')}. {ESTILO}"), params=parametros,
                             headers=cabeceras, timeout=120)
    respuesta.raise_for_status()
    tipo = respuesta.headers.get("Content-Type", "")
    if not tipo.startswith("image/"):
        raise ValueError(f"Pollinations devolvió {tipo or 'una respuesta sin tipo'} en lugar de una imagen")
    return respuesta.content, ("png" if "png" in tipo else "jpg")
