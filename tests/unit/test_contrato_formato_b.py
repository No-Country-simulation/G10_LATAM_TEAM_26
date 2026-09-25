"""
CommunityLab AI - Contrato del motor
El paquete que produce procesar() cumple el Formato B de spec.md (modo simulado: sin IA ni API keys).
"""
import pytest

from src.adapters.ingestion.loaders import interacciones_desde_payload, load_fixture_data
from src.core.orchestrator import procesar, procesar_detalle
from src.domain.schemas import PaqueteDistribucion


@pytest.fixture(scope="module")
def lote():
    payload = load_fixture_data()
    assert payload is not None, "no se pudo cargar data/fixtures/lote_ejemplo_formato_a.json"
    return interacciones_desde_payload(payload)


@pytest.fixture(scope="module")
def detalle(lote):
    interacciones, metadatos = lote
    return procesar_detalle(interacciones, metadatos, simulado=True)


def test_paquete_cumple_formato_b(detalle):
    PaqueteDistribucion.model_validate(detalle["paquete"])


def test_todos_los_activos_nacen_como_borrador(detalle):
    assert detalle["paquete"]["activos"]
    assert {a["estado_curaduria"] for a in detalle["paquete"]["activos"]} == {"borrador"}


def test_formato_p_trae_un_elemento_por_mensaje(lote, detalle):
    interacciones, _ = lote
    ids = [p["tracking"]["message_id"] for p in detalle["procesados"]]
    assert ids == [m["message_id"] for m in interacciones]


def test_simulado_sin_avisos(detalle):
    assert detalle["paquete"]["status"] == "exito"
    assert not any(detalle["avisos"].values())


def test_mensajes_vacios_se_descartan():
    paquete = procesar([{"message_id": "M1", "texto": "   "}, {"message_id": "M2", "texto": "hola a todos"}],
                       simulado=True)
    assert paquete["resumen_comunidad"]["total_interacciones_procesadas"] == 1
