"""
CommunityLab AI - Unit Tests
Resumen con datos de ejemplo cuando la base está vacía, y con los datos reales apenas hay análisis guardados.
"""
import pytest
from fastapi.testclient import TestClient

from src import config
from src.adapters.db import repository


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, "DB_PASSWORD", "")
    monkeypatch.setattr(repository, "SQLITE_PATH", str(tmp_path / "demo.db"))
    repository._motor.cache_clear()
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "clave-de-prueba")
    repository.init_db()  # la API lo hace al arrancar; aquí la base es nueva en cada test
    from src.api import app as modulo
    modulo._FALLOS.clear()
    c = TestClient(modulo.app)
    token = c.post("/api/login", json={"usuario": "admin", "clave": "clave-de-prueba"}).json()["token"]
    c.headers["Authorization"] = f"Bearer {token}"
    yield c
    repository._motor().dispose()
    repository._motor.cache_clear()


def test_resumen_demo_calcula_el_lote_de_ejemplo():
    demo = repository.resumen_demo(config.UMBRALES_POR_TIPO)
    assert demo["mensajes"] == 30 and demo["oportunidades"] > 0
    assert sum(demo["tipos"].values()) == 30 and demo["por_dia"] and demo["canales"] and demo["temas"]
    assert demo["activos"] == {}  # sin borradores ni aprobaciones inventados


def test_resumen_demo_sin_el_archivo_devuelve_none(monkeypatch):
    monkeypatch.setattr(repository, "ARCHIVO_DEMO", "no-existe.json")
    assert repository.resumen_demo(config.UMBRALES_POR_TIPO) is None


def test_la_api_marca_como_demo_el_resumen_de_una_base_vacia(cliente):
    r = cliente.get("/api/resumen").json()
    assert r["demo"] is True and r["mensajes"] == 30 and r["base"]
    assert r["aprobacion"]["total"] == {"aprobados": 0, "descartados": 0, "pendientes": 0}


def test_con_mensajes_guardados_el_resumen_ya_no_es_demo(cliente):
    from src.adapters.db.models import CommunityMessage
    with repository.sesion() as s:
        s.add(CommunityMessage(message_id="Real:MSG-1", channel="general", author_raw="x", author_anon="x",
                               raw_text="hola", clean_text="hola", opportunity_type="FAQ", opportunity_score=0.9))
        s.commit()
    r = cliente.get("/api/resumen").json()
    assert "demo" not in r and r["mensajes"] == 1
