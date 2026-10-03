"""
CommunityLab AI - Contrato del motor
El paquete que produce procesar() cumple el Formato B de spec.md (modo simulado: sin IA ni API keys).
"""
import pytest

from src.adapters.ingestion.loaders import interacciones_desde_payload, load_fixture_data
from src.core.orchestrator import clasificar, generar_contenido, procesar, procesar_detalle
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


def test_por_fases_termina_con_el_mismo_paquete(lote):
    interacciones, metadatos = lote
    completo = procesar(interacciones, metadatos, simulado=True)
    detalle = clasificar(interacciones, metadatos, simulado=True)
    assert detalle["paquete"]["activos"] == []
    assert detalle["paquete"]["resumen_comunidad"] == completo["resumen_comunidad"]

    generacion = generar_contenido(detalle, simulado=True)
    generacion.esperar(timeout=30)
    assert generacion.terminado
    assert detalle["paquete"]["activos"] == completo["activos"]
    assert detalle["paquete"]["status"] == "exito"
    PaqueteDistribucion.model_validate(detalle["paquete"])


def test_mensajes_vacios_se_descartan():
    paquete = procesar([{"message_id": "M1", "texto": "   "}, {"message_id": "M2", "texto": "hola a todos"}],
                       simulado=True)
    assert paquete["resumen_comunidad"]["total_interacciones_procesadas"] == 1


def test_fixtures_oficiales_cumplen_el_contrato():
    """Los fixtures de spec.md son la referencia de los demás módulos: deben validar contra los schemas actuales."""
    import json
    from src.core.agents.detector import es_oportunidad
    from src.domain.schemas import OpportunityType

    paquete = json.load(open("data/fixtures/paquete_ejemplo_formato_b.json", encoding="utf-8"))
    PaqueteDistribucion.model_validate(paquete)

    procesados = json.load(open("data/fixtures/procesados_ejemplo_formato_p.json", encoding="utf-8"))["procesados"]
    tipos_validos = {t.value for t in OpportunityType}
    for p in procesados:
        o = p["opportunity"]
        assert o["type"] in tipos_validos, o
        # opportunity_id solo para los mensajes que superan el umbral de su tipo
        assert bool(o["opportunity_id"]) == es_oportunidad({"type": o["type"], "score": o["opportunity_score"]}), o
    ids = [p["opportunity"]["opportunity_id"] for p in procesados if p["opportunity"]["opportunity_id"]]
    assert paquete["resumen_comunidad"]["oportunidades_detectadas"] == len(ids)
    assert {a["origen"]["opportunity_id"] for a in paquete["activos"]} <= set(ids)
