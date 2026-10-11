"""
CommunityLab AI - Unit Tests
Base de la comunidad (SQLite temporal), subida a OCI Object Storage (cliente simulado) y carga de archivos.
"""
import io
import json

import pytest

from src import config
from src.adapters.cloud.oci_storage import ObjectStorageAdapter
from src.adapters.db import repository
from src.adapters.ingestion.loaders import load_uploaded_json_file, load_fixture_data, interacciones_desde_payload
from src.core.orchestrator import clasificar, generar_contenido


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Base SQLite nueva por test, sin credenciales de Oracle."""
    monkeypatch.setattr(repository, "DB_PASSWORD", "")
    monkeypatch.setattr(repository, "SQLITE_PATH", str(tmp_path / "prueba.db"))
    repository._motor.cache_clear()
    yield repository
    repository._motor().dispose()
    repository._motor.cache_clear()


@pytest.fixture(scope="module")
def lote():
    interacciones, metadatos = interacciones_desde_payload(load_fixture_data())
    detalle = clasificar(interacciones, metadatos, simulado=True)
    generar_contenido(detalle, simulado=True).esperar(10)
    return interacciones, detalle


def test_sin_credenciales_usa_sqlite(base):
    assert not base.usa_oracle() and base.nombre_motor() == "SQLite local"


def test_admin_inicial_y_usuarios_con_bcrypt(base, monkeypatch):
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "clave-de-prueba")
    base.init_db()
    admin = base.verify_user("admin", "clave-de-prueba")
    assert admin and admin.role == "ADMIN"
    assert base.verify_user("admin", "otra") is None
    assert base.register_user("curadora", "secreta").role == "CURATOR"
    assert base.verify_user("curadora", "secreta")
    assert base.register_user("curadora", "otra") is None  # usuario repetido


def test_sin_admin_password_no_crea_admin(base, monkeypatch):
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    base.init_db()
    assert base.verify_user("admin", "") is None


def test_deduplicacion_por_comunidad(base, lote):
    interacciones, detalle = lote
    base.init_db()
    textos = {m["message_id"]: m for m in interacciones}
    assert base.guardar_mensajes(detalle["procesados"], textos, "Comunidad_A") == len(interacciones)
    assert base.guardar_mensajes(detalle["procesados"], textos, "Comunidad_A") == 0  # no duplica
    nuevos, repetidos = base.separar_nuevos(interacciones, "Comunidad_A")
    assert nuevos == [] and repetidos == len(interacciones)
    # el mismo MSG-0001 en otra comunidad es un mensaje distinto
    nuevos, repetidos = base.separar_nuevos(interacciones, "Comunidad_B")
    assert len(nuevos) == len(interacciones) and repetidos == 0


def test_reconoce_las_claves_de_la_version_anterior(base):
    """Filas guardadas sin comunidad (versión anterior): cuentan como procesadas; un id de Discord completo se
    reconoce por sus últimos 6 dígitos."""
    base.init_db()
    from src.adapters.db.models import CommunityMessage
    with base.sesion() as s:
        for mid in ("MSG-0007", "DISC-1552836674617352364", "Otra_Comunidad:MSG-0009"):
            s.add(CommunityMessage(message_id=mid, channel="general", author_raw="x", author_anon="x",
                                   raw_text="hola", clean_text="hola"))
        s.commit()
    mensajes = [{"message_id": i} for i in ("MSG-0007", "DISC-352364", "MSG-0009", "MSG-0010")]
    nuevos, repetidos = base.separar_nuevos(mensajes, "Comunidad_A")
    assert [m["message_id"] for m in nuevos] == ["MSG-0009", "MSG-0010"] and repetidos == 2


def test_activos_se_registran_y_actualizan_su_estado(base, lote):
    interacciones, detalle = lote
    base.init_db()
    paquete = json.loads(json.dumps(detalle["paquete"]))
    base.guardar_mensajes(detalle["procesados"], {m["message_id"]: m for m in interacciones}, "Comunidad_A")
    assert base.guardar_activos(paquete, "Comunidad_A") == len(paquete["activos"])
    paquete["activos"][0]["estado_curaduria"] = "aprobado"
    base.guardar_activos(paquete, "Comunidad_A")
    historico = base.resumen_historico()
    assert historico["mensajes"] == len(interacciones)
    assert sum(historico["activos"].values()) == len(paquete["activos"])  # actualiza, no duplica
    assert historico["activos"]["aprobado"] == 1


class _ClienteFalso:
    def __init__(self, falla=False):
        self.subidos, self.falla = {}, falla

    def put_object(self, namespace_name, bucket_name, object_name, put_object_body, content_type):
        if self.falla:
            raise ConnectionError("bucket inaccesible")
        self.subidos[object_name] = content_type


@pytest.fixture
def paquete_con_imagen(lote, tmp_path):
    paquete = json.loads(json.dumps(lote[1]["paquete"]))
    imagen = tmp_path / "POST-001.jpg"
    imagen.write_bytes(b"\xff\xd8imagen")
    paquete["activos"][0]["imagen"] = {"estado": "lista", "prompt": "a trophy", "ruta": str(imagen), "proveedor": "x"}
    return paquete


def test_oci_sube_paquete_e_imagenes_en_las_rutas_del_spec(paquete_con_imagen, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAIZ", tmp_path)
    cliente = _ClienteFalso()
    resultado = ObjectStorageAdapter(namespace="ns", cliente=cliente).persist_distribution_package(paquete_con_imagen)
    ruta = paquete_con_imagen["almacenamiento_oci"]["ruta_objeto"]
    assert resultado["status"] == "guardado_con_exito" and resultado["imagenes_subidas"] == 1
    assert cliente.subidos[ruta] == "application/json"
    img = f"{ruta.rsplit('/', 1)[0]}/img/{paquete_con_imagen['paquete_id']}/POST-001.jpg"
    assert cliente.subidos[img] == "image/jpeg"
    guardado = json.loads((tmp_path / "data" / "processed" / ruta).read_text(encoding="utf-8"))
    assert guardado["almacenamiento_oci"]["status"] == "guardado_con_exito"
    assert guardado["activos"][0]["imagen"]["ruta_oci"] == img


def test_oci_sin_conexion_o_con_error_deja_copia_local(paquete_con_imagen, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAIZ", tmp_path)
    sin_cliente = ObjectStorageAdapter(namespace="ns", cliente=None)
    sin_cliente.client = None
    assert sin_cliente.persist_distribution_package(paquete_con_imagen)["status"] == "guardado_local"
    con_error = ObjectStorageAdapter(namespace="ns", cliente=_ClienteFalso(falla=True))
    resultado = con_error.persist_distribution_package(paquete_con_imagen)
    assert resultado["status"] == "guardado_local" and "ConnectionError" in resultado["error"]
    assert paquete_con_imagen["almacenamiento_oci"]["status"] == "guardado_local"


def test_carga_de_archivo_subido():
    valido = {"origen_comunidad": "X", "periodo_referencia": "Semana_01",
              "interacciones": [{"message_id": "MSG-0001", "channel": "general", "timestamp": "2026-10-01T00:00:00Z",
                                 "autor": "Ana P.", "texto": "Hola, ¿cómo configuro git?"}]}
    assert len(load_uploaded_json_file(io.StringIO(json.dumps(valido))).interacciones) == 1
    with pytest.raises(ValueError, match="JSON válido"):
        load_uploaded_json_file(io.StringIO("no es json"))
    with pytest.raises(ValueError, match="interacciones"):
        load_uploaded_json_file(io.StringIO(json.dumps({"mensajes": []})))
    with pytest.raises(ValueError, match="Formato A"):
        load_uploaded_json_file(io.StringIO(json.dumps({"interacciones": [{"texto": "sin campos"}]})))
