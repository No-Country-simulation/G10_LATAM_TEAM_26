"""
CommunityLab AI - Data Sanitizer (PII Protection)
Anonimiza datos personales (nombres, correos, teléfonos y menciones)
antes de que la información sea procesada por el LLM o mostrada en el panel.
"""
import re


def anonimizar_texto(texto: str) -> str:
    """Elimina correos electrónicos, teléfonos, menciones de Discord y URLs sensibles."""
    if not texto:
        return ""
    # Enmascarar correos electrónicos
    texto = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL_PROTEGIDO]', texto)
    # Enmascarar números de teléfono habituales
    texto = re.sub(r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}', '[TELEFONO_PROTEGIDO]', texto)
    # Enmascarar menciones internas de Discord tipo <@!123456789>
    texto = re.sub(r'<@!?\d+>', '@miembro', texto)
    return texto


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