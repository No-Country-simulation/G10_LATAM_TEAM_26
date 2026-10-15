"""
CommunityLab AI - Unit Tests
Seguridad del panel (límite de intentos de ingreso, caducidad de sesión, comparación de la clave del admin) y
diagnóstico del cliente de OCI cuando falta la llave.
"""
import time

import pytest
from fastapi.testclient import TestClient

from src import config
from src.adapters.cloud import oci_storage
from src.adapters.db import repository

COOKIE = "cl_sesion"


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(repository, "DB_PASSWORD", "")
    monkeypatch.setattr(repository, "SQLITE_PATH", str(tmp_path / "seg.db"))
    repository._motor.cache_clear()
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "clave-de-prueba")
    from src.api import app as modulo
    modulo._FALLOS.clear()
    yield TestClient(modulo.app)
    modulo._FALLOS.clear()
    repository._motor().dispose()
    repository._motor.cache_clear()


def _login(cliente, clave, usuario="admin"):
    return cliente.post("/api/login", json={"usuario": usuario, "clave": clave})


def test_login_correcto_y_clave_con_tildes_no_rompe_la_comparacion(cliente, monkeypatch):
    assert _login(cliente, "clave-de-prueba").status_code == 200
    monkeypatch.setenv("ADMIN_PASSWORD", "contraseña-ñandú")
    assert _login(cliente, "contraseña-ñandú").status_code == 200
    assert _login(cliente, "contrasena-nandu").status_code == 401


def test_tras_varios_fallos_el_ingreso_se_bloquea_aunque_la_clave_sea_correcta(cliente):
    for _ in range(config.LOGIN_INTENTOS_MAX):
        assert _login(cliente, "mala").status_code == 401
    r = _login(cliente, "clave-de-prueba")
    assert r.status_code == 429 and "intentos" in r.json()["detail"].lower()


def test_el_bloqueo_es_por_usuario_y_no_afecta_a_otros(cliente):
    for _ in range(config.LOGIN_INTENTOS_MAX):
        _login(cliente, "mala", usuario="intruso")
    assert _login(cliente, "mala", usuario="intruso").status_code == 429
    assert _login(cliente, "clave-de-prueba").status_code == 200


def test_el_bloqueo_expira(cliente, monkeypatch):
    for _ in range(config.LOGIN_INTENTOS_MAX):
        _login(cliente, "mala")
    from src.api import app as modulo
    for clave in modulo._FALLOS:
        modulo._FALLOS[clave] = [t - config.LOGIN_BLOQUEO_S - 1 for t in modulo._FALLOS[clave]]
    assert _login(cliente, "clave-de-prueba").status_code == 200


def test_un_ingreso_correcto_borra_los_fallos_previos(cliente):
    for _ in range(config.LOGIN_INTENTOS_MAX - 1):
        _login(cliente, "mala")
    assert _login(cliente, "clave-de-prueba").status_code == 200
    for _ in range(config.LOGIN_INTENTOS_MAX - 1):
        assert _login(cliente, "mala").status_code == 401  # el contador volvió a cero


def test_la_sesion_caduca_por_inactividad_y_el_uso_la_renueva(cliente):
    from src.api import app as modulo
    token = _login(cliente, "clave-de-prueba").json()["token"]
    cabeceras = {"Authorization": f"Bearer {token}"}
    assert cliente.get("/api/sistema", headers=cabeceras).status_code == 200

    modulo._ULTIMO_USO[token] = time.time() - config.SESION_HORAS * 3600 + 60  # le queda un minuto
    assert cliente.get("/api/sistema", headers=cabeceras).status_code == 200
    assert modulo._ULTIMO_USO[token] > time.time() - 5  # el uso renovó el plazo

    modulo._ULTIMO_USO[token] = time.time() - config.SESION_HORAS * 3600 - 1
    assert cliente.get("/api/sistema", headers=cabeceras).status_code == 401
    assert token not in modulo.SESIONES
    # La imagen guardada también respeta la caducidad
    cliente.cookies.set(COOKIE, token, path="/api")
    assert cliente.get("/api/publicaciones/imagen", params={"ruta": "x.png"}).status_code == 401


def test_logout_cierra_la_sesion(cliente):
    token = _login(cliente, "clave-de-prueba").json()["token"]
    cabeceras = {"Authorization": f"Bearer {token}"}
    assert cliente.post("/api/logout", headers=cabeceras).status_code == 200
    assert cliente.get("/api/sistema", headers=cabeceras).status_code == 401


# ─── Diagnóstico de OCI ──────────────────────────────────────────────────────

class _Registro:
    def __init__(self):
        self.avisos = []

    def warning(self, mensaje, *a, **k):
        self.avisos.append(mensaje)


@pytest.fixture()
def avisos(monkeypatch):
    registro = _Registro()
    monkeypatch.setattr(oci_storage, "logger", registro)
    for nombre in ("OCI_CONFIG_FILE", "OCI_USER_OCID", "OCI_TENANCY_OCID", "OCI_FINGERPRINT", "OCI_KEY_FILE"):
        monkeypatch.delenv(nombre, raising=False)
    return registro.avisos


def test_oci_sin_ninguna_variable_no_molesta(avisos):
    assert oci_storage._cliente_oci() is None
    assert avisos == []


def test_oci_con_llave_inexistente_dice_que_ruta_busco(avisos, monkeypatch, tmp_path):
    monkeypatch.setenv("OCI_USER_OCID", "ocid1.user.oc1..prueba")
    monkeypatch.setenv("OCI_KEY_FILE", str(tmp_path / "no_existe.pem"))
    assert oci_storage._cliente_oci() is None
    assert len(avisos) == 1 and "no_existe.pem" in avisos[0] and "llave privada" in avisos[0]
    assert "ocid1" not in avisos[0]  # el aviso no filtra identificadores


def test_oci_con_configuracion_incompleta_dice_que_falta(avisos, monkeypatch):
    monkeypatch.setenv("OCI_KEY_FILE", "data/oci_api_key.pem")
    assert oci_storage._cliente_oci() is None
    assert len(avisos) == 1 and "OCI_USER_OCID" in avisos[0]


def test_oci_config_file_inexistente_se_avisa(avisos, monkeypatch, tmp_path):
    monkeypatch.setenv("OCI_CONFIG_FILE", str(tmp_path / "config"))
    assert oci_storage._cliente_oci() is None
    assert any("OCI_CONFIG_FILE" in a for a in avisos)


# ─── Sesión de las imágenes: cookie HttpOnly en vez de token en la URL ───────

def test_login_deja_una_cookie_httponly_y_logout_la_borra(cliente):
    r = _login(cliente, "clave-de-prueba")
    cookie = r.headers["set-cookie"].lower()
    assert f"{COOKIE}={r.json()['token']}".lower() in cookie
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
    assert "secure" not in cookie  # por HTTP plano (desarrollo) no se marca Secure
    # Sin plazo propio: si caducara a las SESION_HORAS del login, una sesión activa se quedaría sin imágenes
    assert "max-age" not in cookie and "expires" not in cookie
    out =cliente.post("/api/logout", headers={"Authorization": f"Bearer {r.json()['token']}"})
    assert out.status_code == 200 and "max-age=0" in out.headers["set-cookie"].lower()


def test_la_cookie_es_secure_detras_de_un_proxy_https(cliente):
    r = cliente.post("/api/login", json={"usuario": "admin", "clave": "clave-de-prueba"},
                     headers={"X-Forwarded-Proto": "https"})
    assert "secure" in r.headers["set-cookie"].lower()


def test_las_imagenes_exigen_la_cookie_y_ya_no_aceptan_el_token_en_la_url(cliente):
    token = _login(cliente, "clave-de-prueba").json()["token"]
    ruta = {"ruta": "generated/2026-10-01/img/PKG/POST-001.png"}
    cliente.cookies.clear()
    assert cliente.get("/api/publicaciones/imagen", params=ruta).status_code == 401
    assert cliente.get("/api/publicaciones/imagen", params={**ruta, "token": token}).status_code == 401  # ya no vale
    # con la cookie la sesión es válida: se llega a la validación de la ruta o al bucket, no al 401
    cliente.cookies.set(COOKIE, token, path="/api")
    assert cliente.get("/api/publicaciones/imagen", params=ruta).status_code != 401
    cliente.cookies.clear()
    assert cliente.get("/api/activos/POST-001/imagen", params={"token": token}).status_code == 401


def test_la_imagen_de_un_borrador_se_sirve_solo_con_la_cookie(cliente, tmp_path):
    from src.api import app as modulo
    token = _login(cliente, "clave-de-prueba").json()["token"]
    imagen = tmp_path / "POST-001.png"
    imagen.write_bytes(b"\x89PNG-de-prueba")
    modulo.SESIONES[token].paquete = {"activos": [{"activo_id": "POST-001", "imagen": {"ruta": str(imagen)}}]}
    cliente.cookies.clear()
    assert cliente.get("/api/activos/POST-001/imagen").status_code == 401
    cliente.cookies.set(COOKIE, token, path="/api")
    r = cliente.get("/api/activos/POST-001/imagen")
    assert r.status_code == 200 and r.content == b"\x89PNG-de-prueba"
    cliente.cookies.clear()
