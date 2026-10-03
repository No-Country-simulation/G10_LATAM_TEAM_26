"""
CommunityLab AI - Unit Tests
Imágenes de las publicaciones: adaptador de Pollinations y generación en segundo plano (servicio simulado).
"""
import pytest

from src import config
from src.adapters import imagenes
from src.core.agents.esquemas_llm import Borrador
from src.core.agents.strategist import construir_activo
from src.core.generacion import ImagenesEnSegundoPlano


def _paquete(*scores):
    activos = [{"activo_id": f"POST-{i:03d}", "formato": "post_linkedin", "origen": {"score": s},
                "imagen": {"estado": "pendiente", "prompt": f"objeto {i}", "ruta": None, "proveedor": None}}
               for i, s in enumerate(scores, start=1)]
    return {"paquete_id": "PKG-2026-S40-120000", "activos": activos,
            "almacenamiento_oci": {"ruta_objeto": "generated/2026-10-01/PKG-2026-S40-120000.json"}}


@pytest.fixture
def raiz_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAIZ", tmp_path)
    return tmp_path


def test_genera_de_mayor_a_menor_score_y_guarda_el_archivo(raiz_temporal):
    orden = []

    def generar(prompt, formato, semilla):
        orden.append(prompt)
        return b"\xff\xd8imagen", "jpg"

    paquete = _paquete(0.7, 0.95, 0.8)
    hilo = ImagenesEnSegundoPlano(paquete, generar=generar, intervalo=0).iniciar()
    hilo.esperar(5)
    assert hilo.terminado and hilo.generadas == 3
    assert orden == ["objeto 2", "objeto 3", "objeto 1"]
    ruta = raiz_temporal / "data/processed/generated/2026-10-01/img/PKG-2026-S40-120000/POST-002.jpg"
    assert ruta.read_bytes() == b"\xff\xd8imagen"
    assert {a["imagen"]["estado"] for a in paquete["activos"]} == {"lista"}


def test_un_fallo_marca_error_y_sigue_con_las_demas(raiz_temporal):
    def generar(prompt, formato, semilla):
        if prompt == "objeto 1":
            raise ConnectionError("servicio caído")
        return b"img", "png"

    paquete = _paquete(0.9, 0.8)
    ImagenesEnSegundoPlano(paquete, generar=generar, intervalo=0).iniciar().esperar(5)
    estados = {a["activo_id"]: a["imagen"] for a in paquete["activos"]}
    assert estados["POST-001"]["estado"] == "error" and estados["POST-001"]["detalle"] == "ConnectionError"
    assert estados["POST-002"]["estado"] == "lista"


def test_maximo_de_imagenes_omite_el_resto(raiz_temporal):
    paquete = _paquete(0.9, 0.8, 0.7)
    ImagenesEnSegundoPlano(paquete, generar=lambda *a, **k: (b"img", "png"), intervalo=0, maximo=1).iniciar().esperar(5)
    assert [a["imagen"]["estado"] for a in paquete["activos"]] == ["lista", "omitida", "omitida"]


def test_detener_corta_la_cola(raiz_temporal):
    paquete = _paquete(0.9, 0.8, 0.7)
    hilo = ImagenesEnSegundoPlano(paquete, generar=lambda *a, **k: (b"img", "png"), intervalo=30)
    hilo.iniciar()
    hilo.detener()
    hilo.esperar(5)
    assert hilo.terminado and hilo.generadas <= 1


def test_el_activo_solo_trae_imagen_cuando_se_pide():
    pieza = {"activo_id": "FAQ-001", "formato": "sugerencia_faq",
             "opp": {"message_id": "MSG-0001", "opportunity_id": "OPP-001", "texto": "¿Cómo uso git?",
                     "sentiment": "neutral", "topics": ["git"], "type": "FAQ", "score": 0.8, "reason": "duda"}}
    borrador = Borrador(pieza_id="x", titulo="¿Cómo uso git?", cuerpo="Usa git status.", prompt_imagen="a git logo")
    assert "imagen" not in construir_activo(pieza, borrador)
    con = construir_activo(pieza, borrador, con_imagen=True)
    assert con["imagen"] == {"estado": "pendiente", "prompt": "a git logo", "ruta": None, "proveedor": None}
    sin_prompt = construir_activo(pieza, Borrador(pieza_id="x", titulo="t", cuerpo="c"), con_imagen=True)
    assert "lightbulb" in sin_prompt["imagen"]["prompt"]  # objeto por defecto según el tipo


class _Respuesta:
    def __init__(self, tipo, contenido=b"img"):
        self.headers = {"Content-Type": tipo}
        self.content = contenido

    def raise_for_status(self):
        pass


def test_adaptador_pide_imagen_privada_y_sin_logo_solo_con_token(monkeypatch):
    llamadas = []
    monkeypatch.setattr(imagenes.requests, "get",
                        lambda url, params, headers, timeout: llamadas.append((url, params, headers)) or _Respuesta("image/jpeg"))
    monkeypatch.setattr(config, "POLLINATIONS_TOKEN", "")
    assert imagenes.generar("a trophy", "post_linkedin", semilla=7) == (b"img", "jpg")
    url, params, headers = llamadas[-1]
    assert params["private"] == "true" and params["width"] == 1200 and "nologo" not in params and not headers
    monkeypatch.setattr(config, "POLLINATIONS_TOKEN", "token-de-prueba")
    imagenes.generar("a trophy", "sugerencia_faq")
    url, params, headers = llamadas[-1]
    assert params["nologo"] == "true" and headers["Authorization"] == "Bearer token-de-prueba"


def test_adaptador_rechaza_respuestas_que_no_son_imagen(monkeypatch):
    monkeypatch.setattr(imagenes.requests, "get", lambda *a, **k: _Respuesta("text/html"))
    with pytest.raises(ValueError):
        imagenes.generar("a trophy", "post_linkedin")


def test_el_limite_del_servicio_reencola_la_imagen(raiz_temporal):
    import requests

    def limite():
        error = requests.HTTPError("402")
        error.response = type("R", (), {"status_code": 402})()
        return error

    respuestas = [limite(), None]

    def generar(prompt, formato, semilla):
        r = respuestas.pop(0)
        if r:
            raise r
        return b"img", "png"

    paquete = _paquete(0.9)
    hilo = ImagenesEnSegundoPlano(paquete, generar=generar, intervalo=0).iniciar()
    hilo.esperar(5)
    imagen = paquete["activos"][0]["imagen"]
    assert imagen["estado"] == "lista" and imagen["intentos"] == 1 and hilo.fallidas == 0
