"""
CommunityLab AI - Unit Tests
Anonimización de PII y reglas de oportunidad (sin llamadas a la IA).
"""
from src.core.agents.detector import es_oportunidad
from src.utils.sanitizer import anonimizar_autor, anonimizar_texto
from src.utils.texto import hashtags, pasos_en_lineas


def test_anonimizar_autor():
    assert anonimizar_autor("Mariana Souza") == "Mariana S."
    assert anonimizar_autor("Lucas Albuquerque") == "Lucas A."
    assert anonimizar_autor("Pedro") == "Pedro"
    assert anonimizar_autor("") == "Miembro Anónimo"


def test_anonimizar_texto_pii():
    limpio = anonimizar_texto("Hola, escríbeme a valeria@correo.com para pasarte el link.")
    assert "valeria@correo.com" not in limpio
    assert "[EMAIL_PROTEGIDO]" in limpio
    assert "@miembro" in anonimizar_texto("Muchas gracias a <@!123456789> por la ayuda.")


def test_telefono_completo_se_enmascara():
    limpio = anonimizar_texto("mi celular es +51 987 654 321, escríbeme")
    assert "987" not in limpio and "321" not in limpio
    assert "[TELEFONO_PROTEGIDO]" in limpio


def test_cifras_y_anios_no_son_telefonos():
    texto = "desde 2026 estudio; después de 23 postulaciones lo dejé en 20 minutos"
    assert anonimizar_texto(texto) == texto


def test_umbral_por_tipo():
    assert es_oportunidad({"type": "SUCCESS_STORY", "score": 0.8})
    assert not es_oportunidad({"type": "SUCCESS_STORY", "score": 0.79})
    assert es_oportunidad({"type": "FAQ", "score": 0.7})
    assert not es_oportunidad({"type": "CONSULTA_OPERATIVA", "score": 0.95})
    assert not es_oportunidad({"type": "OTRO", "score": 1.0})


def test_hashtags_pegados_se_separan():
    assert hashtags(["#AnalistaBI#LogroTech", "Python", "#React #NodeJS"]) == \
        ["#AnalistaBI", "#LogroTech", "#Python", "#React", "#NodeJS"]


def test_pasos_numerados_en_lineas_separadas():
    assert pasos_en_lineas("Sigue estos pasos: 1. Activa el entorno. 2. Instala las dependencias.") == \
        "Sigue estos pasos:\n1. Activa el entorno.\n2. Instala las dependencias."
    sin_secuencia = "Usa Python 3. Luego revisa el paso 2. del instalador."
    assert pasos_en_lineas(sin_secuencia) == sin_secuencia
