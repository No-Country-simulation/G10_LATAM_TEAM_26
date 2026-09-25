"""
CommunityLab AI - Data Sanitizer (PII Protection)
Anonimiza datos personales (nombres, correos, teléfonos y menciones)
antes de que la información sea procesada por el LLM o mostrada en el panel.
"""
import re

_EMAIL = re.compile(r"[\w.-]+@[\w.-]+\.\w+")
_MENCION = re.compile(r"<@!?\d+>")
# Exige 6+ dígitos para no enmascarar años, cifras o duraciones ("2026", "20 minutos")
_TELEFONO = re.compile(r"(?<![\w+])(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3}[\s.-]?\d{3,4}(?!\w)")


def anonimizar_texto(texto: str) -> str:
    """Enmascara correos, menciones de Discord y teléfonos."""
    if not texto:
        return ""
    texto = _EMAIL.sub("[EMAIL_PROTEGIDO]", texto)
    # Las menciones van antes que los teléfonos: sus IDs numéricos parecen teléfonos
    texto = _MENCION.sub("@miembro", texto)
    return _TELEFONO.sub("[TELEFONO_PROTEGIDO]", texto)


def anonimizar_autor(autor: str) -> str:
    """
    Conserva el primer nombre y la inicial del apellido para mantener
    el toque humano y la voz del testimonio sin exponer la identidad completa.
    Ejemplo: 'Mariana Souza' -> 'Mariana S.'
    """
    if not autor:
        return "Miembro Anónimo"
    partes = autor.strip().split()
    if len(partes) <= 1:
        return autor
    return f"{partes[0]} {partes[1][0]}."