"""
CommunityLab AI - Unit Tests
Llamada de cobertura entre proveedores y caché de clasificaciones (proveedores simulados, sin llamadas a la IA).
"""
import time

import pytest

from src import config
from src.adapters import cache_clasificacion
from src.adapters.llm import proveedores
from src.core.agents import classifier
from src.core.agents.esquemas_llm import Candidato, ClasificacionBreve, ClasificacionCompacta


@pytest.fixture
def cadena_de_cuatro(monkeypatch):
    """Gemini titular, dos alternos de Gemini y Groq, con cobertura cada 0.2 s."""
    monkeypatch.setenv(config.PROVEEDORES["gemini"]["key"], "x")
    monkeypatch.setenv(config.PROVEEDORES["groq"]["key"], "x")
    monkeypatch.setattr(config, "PROVEEDOR", "gemini")
    monkeypatch.setattr(config, "RESPALDO", "groq")
    monkeypatch.setattr(config, "ALTERNOS_GEMINI", ["alterno-1", "alterno-2"])
    monkeypatch.setattr(config, "COBERTURA_S", 0.2)
    return [nombre for _, nombre in proveedores.cadena("analisis")]


def _falsos(demoras, fallan=()):
    """Modelos simulados: cada uno tarda lo indicado (por posición en la cadena) y responde su propio nombre."""
    def invocar_en(eslabon, *args, ultimo=True):
        orden = [n for _, n in proveedores.cadena(args[2])]
        time.sleep(demoras[orden.index(eslabon[1])])
        if orden.index(eslabon[1]) in fallan:
            raise RuntimeError("falla simulada")
        return eslabon[1]
    return invocar_en


def test_cadena_prueba_alternos_de_gemini_antes_que_groq(cadena_de_cuatro):
    assert cadena_de_cuatro[1:3] == ["alterno-1", "alterno-2"]
    assert cadena_de_cuatro[3] == config.PROVEEDORES["groq"]["analisis"]


def test_cobertura_gana_el_primer_alterno_si_el_titular_se_demora(cadena_de_cuatro, monkeypatch):
    monkeypatch.setattr(proveedores, "_invocar_en", _falsos([2.0, 0.05, 2.0, 2.0]))
    inicio = time.perf_counter()
    assert proveedores.invocar(None, None, "analisis", 0, {}) == "alterno-1"
    assert time.perf_counter() - inicio < 1.0


def test_sin_demora_responde_el_titular(cadena_de_cuatro, monkeypatch):
    monkeypatch.setattr(proveedores, "_invocar_en", _falsos([0.05, 0.05, 0.05, 0.05]))
    assert proveedores.invocar(None, None, "analisis", 0, {}) == cadena_de_cuatro[0]


def test_error_conmuta_al_siguiente_sin_esperar(cadena_de_cuatro, monkeypatch):
    monkeypatch.setattr(proveedores, "_invocar_en", _falsos([0.0, 0.0, 0.05, 0.05], fallan=(0, 1)))
    inicio = time.perf_counter()
    assert proveedores.invocar(None, None, "analisis", 0, {}) == "alterno-2"
    assert time.perf_counter() - inicio < 0.2


def test_cobertura_espera_al_titular_si_los_demas_fallan(cadena_de_cuatro, monkeypatch):
    monkeypatch.setattr(proveedores, "_invocar_en", _falsos([0.7, 0.0, 0.0, 0.0], fallan=(1, 2, 3)))
    assert proveedores.invocar(None, None, "analisis", 0, {}) == cadena_de_cuatro[0]


def test_redaccion_conmuta_solo_ante_errores(cadena_de_cuatro, monkeypatch):
    monkeypatch.setattr(proveedores, "_invocar_en", _falsos([0.4, 0.0, 0.0, 0.0]))
    assert proveedores.invocar(None, None, "redaccion", 0, {}) == proveedores.cadena("redaccion")[0][1]


def test_cache_evita_volver_a_llamar_a_la_ia(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARCHIVO_CACHE", tmp_path / "cache.json")
    monkeypatch.setattr(config, "USAR_CACHE", True)
    monkeypatch.setattr(cache_clasificacion, "_memoria", None)
    llamadas = []

    def invocar_lotes(prompt, esquema, rol, temperature, entradas, al_completar=None):
        llamadas.append(len(entradas))
        respuesta = ClasificacionCompacta(
            mensajes=[ClasificacionBreve(message_id="MSG-0001", sentiment="positive", topics=["empleo"],
                                         type="SUCCESS_STORY")],
            candidatos=[Candidato(message_id="MSG-0001", score=0.9, reason="consiguió trabajo")])
        al_completar(0, respuesta)
        return [respuesta]

    monkeypatch.setattr(classifier, "invocar_lotes", invocar_lotes)
    estado = {"interacciones_originales": [{"message_id": "MSG-0001", "texto": "¡Me contrataron!", "canal": "logros",
                                            "reacciones": 3, "respuestas": 1}]}
    primera = classifier.community_classifier(estado)
    segunda = classifier.community_classifier(estado)
    assert llamadas == [1]
    assert primera == segunda
    assert segunda["oportunidades"][0]["opportunity_id"] == "OPP-001"


def test_avance_lote_por_lote_en_modo_simulado():
    from src.core import orchestrator
    mensajes = [{"message_id": f"MSG-{i:04d}", "texto": f"Mensaje de prueba número {i}", "canal": "general"}
                for i in range(1, 26)]
    tandas = []
    detalle = orchestrator.clasificar(mensajes, {}, simulado=True, al_avanzar=lambda filas: tandas.append(len(filas)))
    assert sum(tandas) == 25
    assert len(detalle["procesados"]) == 25

    en_segundo_plano = orchestrator.clasificar_en_segundo_plano(mensajes, {}, simulado=True)
    en_segundo_plano.esperar(10)
    assert en_segundo_plano.terminado and en_segundo_plano.error is None
    assert len(en_segundo_plano.parciales) == en_segundo_plano.total == 25
    assert en_segundo_plano.detalle["paquete"]["resumen_comunidad"]["total_interacciones_procesadas"] == 25
