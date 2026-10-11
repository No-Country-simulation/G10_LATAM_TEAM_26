"""
CommunityLab AI - Unit Tests
API web (FastAPI) en modo simulado: login, lote, análisis en segundo plano, curaduría y descarga del media kit.
"""
import io
import json
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from src.adapters.db import repository


@pytest.fixture(scope="module")
def cliente(tmp_path_factory):
    repository.DB_PASSWORD = ""
    repository.SQLITE_PATH = str(tmp_path_factory.mktemp("db") / "api.db")
    repository._motor.cache_clear()
    from src.api.app import app
    yield TestClient(app)
    repository._motor().dispose()
    repository._motor.cache_clear()


@pytest.fixture(scope="module")
def cabeceras(cliente):
    mp = pytest.MonkeyPatch()
    mp.setenv("ADMIN_USER", "admin")
    mp.setenv("ADMIN_PASSWORD", "clave-de-prueba")
    assert cliente.post("/api/login", json={"usuario": "admin", "clave": "otra"}).status_code == 401
    r = cliente.post("/api/login", json={"usuario": "admin", "clave": "clave-de-prueba"})
    mp.undo()
    assert r.status_code == 200 and r.json()["rol"] == "ADMIN"
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _esperar(cliente, cabeceras, fase="listo", limite=30):
    for _ in range(limite * 10):
        estado = cliente.get("/api/analisis", headers=cabeceras).json()
        if estado["fase"] in (fase, "error"):
            return estado
        time.sleep(0.1)
    raise AssertionError(f"el análisis no llegó a '{fase}'")


def test_sin_sesion_responde_401(cliente):
    assert cliente.get("/api/analisis").status_code == 401


def test_flujo_completo_en_modo_simulado(cliente, cabeceras):
    lote = cliente.get("/api/dataset", headers=cabeceras).json()
    assert lote["fuente"] == "estandar" and lote["total"] == 30
    r = cliente.post("/api/analisis", headers=cabeceras, json={"cantidad": 30, "simulado": True})
    assert r.json() == {"mensajes": 30, "repetidos": 0, "quedan": 0}

    estado = _esperar(cliente, cabeceras)
    assert estado["fase"] == "listo" and len(estado["mensajes"]) == 30
    assert estado["salud"]["etiqueta"] and estado["paquete"]["activos"] == estado["redaccion"]["total"]
    assert any(m["es_oportunidad"] for m in estado["mensajes"])

    activos = cliente.get("/api/paquete", headers=cabeceras).json()["activos"]
    primero = activos[0]["activo_id"]
    aprobado = cliente.patch(f"/api/activos/{primero}", headers=cabeceras, json={"estado": "aprobado"}).json()
    assert aprobado["estado_curaduria"] == "aprobado"
    campo = next(iter(aprobado["contenido"]))
    editado = cliente.patch(f"/api/activos/{primero}", headers=cabeceras,
                            json={"contenido": {campo: "texto nuevo"}}).json()
    assert editado["estado_curaduria"] == "borrador"  # editar un aprobado lo devuelve a revisión
    cliente.patch(f"/api/activos/{primero}", headers=cabeceras, json={"estado": "aprobado"})

    kit = zipfile.ZipFile(io.BytesIO(cliente.get("/api/paquete/media-kit", headers=cabeceras).content))
    assert any(n.endswith(".txt") for n in kit.namelist())
    paquete = json.loads(cliente.get("/api/paquete/json", headers=cabeceras).content)
    assert paquete["activos"][0]["estado_curaduria"] == "aprobado"


def test_archivo_invalido_explica_el_error(cliente, cabeceras):
    r = cliente.post("/api/dataset/archivo", headers=cabeceras, json={"nombre": "x.json", "contenido": "no es json"})
    assert r.status_code == 400 and "JSON" in r.json()["detail"]


def test_solo_admin_crea_usuarios(cliente, cabeceras):
    r = cliente.post("/api/usuarios", headers=cabeceras, json={"usuario": "curadora", "clave": "x1", "rol": "CURATOR"})
    assert r.status_code == 200
    curadora = cliente.post("/api/login", json={"usuario": "curadora", "clave": "x1"}).json()
    r = cliente.post("/api/usuarios", headers={"Authorization": f"Bearer {curadora['token']}"},
                     json={"usuario": "otro", "clave": "x"})
    assert r.status_code == 403


def test_comunidades_de_discord_solo_admin_y_sin_token(cliente, cabeceras, tmp_path, monkeypatch):
    from src.adapters.ingestion import discord_comunidades as comunidades
    from src.api import app as modulo
    monkeypatch.setattr(comunidades, "CARPETA_COMUNIDADES", tmp_path)
    monkeypatch.setattr(comunidades, "ARCHIVO", tmp_path / "comunidades.json")
    monkeypatch.setattr(modulo.DiscordAPI, "identidad",
                        lambda self: {"aplicacion": "Bot", "servidores": [{"id": "9", "nombre": "Comunidad X"}]})
    r = cliente.post("/api/discord/comunidades", headers=cabeceras,
                     json={"nombre": "Comunidad X", "token": "token-secreto-123456", "servidor_id": "9"})
    assert r.status_code == 200 and "token" not in r.json() and r.json()["token_final"] == "…3456"
    lista = cliente.get("/api/discord/comunidades", headers=cabeceras).json()
    assert [c["nombre"] for c in lista][-1] == "Comunidad X" and all("token" not in c for c in lista)
    r = cliente.post("/api/discord/comunidades", headers=cabeceras,
                     json={"nombre": "Otra", "token": "token-secreto-123456", "servidor_id": "no-existe"})
    assert r.status_code == 400
    assert cliente.delete(f"/api/discord/comunidades/{lista[-1]['id']}", headers=cabeceras).status_code == 200


def test_analizar_n_toma_los_siguientes_pendientes(monkeypatch):
    """Si los primeros mensajes del lote ya se analizaron, "analizar 5" toma los 5 siguientes que faltan."""
    from src.api import espacio as modulo
    capturados = {}
    monkeypatch.setattr(modulo.repository, "separar_nuevos",
                        lambda inter, comunidad: (inter[10:], 10))  # los 10 primeros ya estaban en la base
    monkeypatch.setattr(modulo, "clasificar_en_segundo_plano",
                        lambda inter, meta, simulado: capturados.setdefault("ids", [m["message_id"] for m in inter]))
    monkeypatch.setattr(modulo.Espacio, "_seguir", lambda self, c: None)
    e = modulo.Espacio("x", "ADMIN")
    todos = [m.message_id for m in e.dataset.interacciones]
    assert e.analizar(5, simulado=False, omitir_repetidos=True) == {"mensajes": 5, "repetidos": 10, "quedan": 15}
    assert capturados["ids"] == todos[10:15]
