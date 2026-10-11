"""
CommunityLab AI - Unit Tests
Discord bajo demanda (API REST con una sesión simulada) y normalización de las capturas al Formato A.
"""
import json

from src.adapters.ingestion.discord_api import DiscordAPI
from src.adapters.ingestion.loaders import load_discord_raw_stream, payload_desde_discord


def _msg(id_, ts, texto, canal="general", bot=False):
    return {"id": id_, "timestamp": ts, "content": texto, "clean_content": texto, "channel": {"name": canal},
            "author": {"display_name": "Ana", "bot": bot}, "reactions": [{"count": 2}], "attachments": []}


def test_ordena_del_mas_reciente_sin_repetidos_ni_bots():
    registros = [
        _msg("1425000000000111111", "2026-09-18T10:00:00+00:00", "viejo"),
        _msg("1426000000000222222", "2026-10-07T19:39:00+00:00", "nuevo", canal="dudas-tecnicas"),
        _msg("1425500000000555555", "2026-10-01T12:00:00+00:00", "del 1 de octubre"),
        _msg("1425000000000111111", "2026-09-18T10:00:00+00:00", "viejo (editado)"),  # recapturado
        _msg("1426000000000333333", "2026-10-07T20:00:00+00:00", "soy un bot", bot=True),
        _msg("1426000000000444444", "2026-10-07T20:01:00+00:00", "   "),
    ]
    payload = payload_desde_discord(registros)
    assert [m.texto for m in payload.interacciones] == ["nuevo", "del 1 de octubre", "viejo (editado)"]
    assert payload.interacciones[0].message_id == "DISC-222222"
    assert payload.interacciones[0].tipo_declarado == "pregunta_tecnica"
    assert payload.interacciones[0].metadata["reacciones"] == 2


def test_lee_todos_los_dias_y_suma_los_recientes(tmp_path):
    for dia, msg in (("2026-10-06", _msg("1", "2026-10-06T10:00:00Z", "ayer")),
                     ("2026-10-07", _msg("2", "2026-10-07T10:00:00Z", "hoy"))):
        (tmp_path / dia).mkdir()
        (tmp_path / dia / "discord_capturas.jsonl").write_text(json.dumps(msg) + "\n", encoding="utf-8")
    payload = load_discord_raw_stream(str(tmp_path), recientes=[_msg("3", "2026-10-07T11:00:00Z", "de la API")])
    assert [m.texto for m in payload.interacciones] == ["de la API", "hoy", "ayer"]
    assert load_discord_raw_stream(str(tmp_path / "vacio")) is None


class _Respuesta:
    def __init__(self, status, datos):
        self.status_code, self._datos = status, datos

    def json(self):
        return self._datos

    def raise_for_status(self):
        assert self.status_code < 400


def _mensaje(id_, texto, tipo=0, autor="axel", menciones=()):
    return {"id": id_, "type": tipo, "timestamp": f"2026-10-07T19:{int(id_) % 60:02d}:00Z", "content": texto,
            "author": {"id": "7", "username": autor, "global_name": autor.capitalize()},
            "mentions": list(menciones), "reactions": [{"emoji": {"name": "🔥"}, "count": 3}]}


class _SesionFalsa:
    """Un servidor con #general (con un hilo), #privado (sin permiso) y un canal de voz. `general` simula el
    historial completo: responde a `after` con lo posterior y sin cursor con lo más reciente."""
    def __init__(self):
        self.pedidos = []
        self.general = [_mensaje("101", "hola <@7> <:python:55>", menciones=[{"id": "7", "username": "axel",
                                                                                "global_name": "Axel"}]),
                        {"id": "100", "type": 7, "timestamp": "2026-10-07T19:00:00Z", "content": "",
                         "author": {"id": "8", "username": "nuevo"}}]  # aviso de unión al servidor

    def get(self, url, params=None, timeout=None, headers=None):
        assert headers["Authorization"] == "Bot token-falso"
        ruta = url.split("/v10", 1)[1]
        self.pedidos.append((ruta, dict(params or {})))
        if ruta == "/users/@me/guilds":
            return _Respuesta(200, [{"id": "9", "name": "Comunidad"}])
        if ruta == "/guilds/9/channels":
            return _Respuesta(200, [{"id": "10", "name": "general", "type": 0},
                                    {"id": "11", "name": "privado", "type": 0},
                                    {"id": "12", "name": "Voz", "type": 2}])
        if ruta == "/guilds/9/threads/active":
            return _Respuesta(200, {"threads": [{"id": "20", "name": "Duda de LangGraph", "type": 11, "parent_id": "10"}]})
        if ruta.endswith("/threads/archived/public"):
            return _Respuesta(403 if "/11/" in ruta else 200, {"threads": []})
        if ruta == "/channels/11/messages":
            return _Respuesta(403, {"code": 50001})
        if ruta == "/channels/20/messages":
            return _Respuesta(200, [] if (params or {}).get("after") else [_mensaje("150", "¿cómo comparto estado?")])
        assert ruta == "/channels/10/messages", ruta
        despues = (params or {}).get("after")
        if despues:
            return _Respuesta(200, [m for m in self.general if int(m["id"]) > int(despues)])
        return _Respuesta(200, sorted(self.general, key=lambda m: -int(m["id"]))[:params["limit"]])


def test_api_trae_canales_e_hilos_legibles_y_omite_avisos(monkeypatch):
    monkeypatch.delenv("SERVIDORES_OBSERVADOS", raising=False)
    monkeypatch.delenv("CANALES_OBSERVADOS", raising=False)
    sesion = _SesionFalsa()
    registros = DiscordAPI("token-falso", sesion).mensajes_recientes()
    assert sorted(r["id"] for r in registros) == ["101", "150"]
    general = next(r for r in registros if r["id"] == "101")
    assert general["clean_content"] == "hola @Axel :python:" and general["author"]["display_name"] == "Axel"
    hilo = next(r for r in registros if r["id"] == "150")
    assert hilo["channel"]["name"] == "general" and hilo["channel"]["hilo"] == "Duda de LangGraph"
    assert not any(r.startswith("/channels/12/") for r, _ in sesion.pedidos)  # los canales de voz no se consultan
    assert payload_desde_discord(registros).interacciones[0].metadata["reacciones"] == 3


def test_sincronizar_trae_solo_lo_nuevo(tmp_path, monkeypatch):
    monkeypatch.delenv("SERVIDORES_OBSERVADOS", raising=False)
    monkeypatch.delenv("CANALES_OBSERVADOS", raising=False)
    sesion = _SesionFalsa()
    api = DiscordAPI("token-falso", sesion)
    assert api.sincronizar(tmp_path)["nuevos"] == 2
    cursores = json.loads((tmp_path / "cursores.json").read_text(encoding="utf-8"))
    assert cursores == {"10": "101", "20": "150"}

    sesion.general.append(_mensaje("102", "llegó después", autor="ana"))
    assert api.sincronizar(tmp_path)["nuevos"] == 1  # solo el mensaje nuevo
    pedidos_general = [p for r, p in sesion.pedidos if r == "/channels/10/messages"]
    assert pedidos_general[-1].get("after") == "101"
    payload = load_discord_raw_stream(str(tmp_path))
    assert [m.texto for m in payload.interacciones][:1] == ["llegó después"]
    assert len(payload.interacciones) == 3  # sin repetidos


def test_api_filtra_canales_y_sin_token_no_consulta(monkeypatch):
    monkeypatch.setenv("CANALES_OBSERVADOS", "privado")
    assert DiscordAPI("token-falso", _SesionFalsa()).mensajes_recientes() == []
    assert DiscordAPI("", _SesionFalsa()).mensajes_recientes() == []
    assert DiscordAPI("", _SesionFalsa()).sincronizar() == {"nuevos": 0, "canales": 0}
    assert not DiscordAPI("pega-tu-token-aqui").configurado


class _BucketFalso:
    def __init__(self):
        self.objetos = {}

    def subir(self, ruta, datos, tipo="application/octet-stream"):
        self.objetos[ruta] = datos

    def listar(self, prefijo):
        return [n for n in self.objetos if n.startswith(prefijo)]

    def leer(self, ruta):
        return self.objetos[ruta]


def test_sube_lo_nuevo_a_raw_y_lo_recupera_con_el_disco_vacio(tmp_path, monkeypatch):
    monkeypatch.delenv("SERVIDORES_OBSERVADOS", raising=False)
    monkeypatch.delenv("CANALES_OBSERVADOS", raising=False)
    sesion, bucket = _SesionFalsa(), _BucketFalso()
    api = DiscordAPI("token-falso", sesion)
    resumen = api.sincronizar(tmp_path / "a", almacen=bucket)
    assert resumen["nuevos"] == 2 and resumen["en_oci"].startswith("raw/") and list(bucket.objetos) == [resumen["en_oci"]]
    assert api.sincronizar(tmp_path / "a", almacen=bucket)["en_oci"] is None  # sin nuevos no sube nada

    # Otro servidor con el disco vacío: recupera lo leído y sigue desde los mismos cursores
    sesion.general.append(_mensaje("102", "llegó después", autor="ana"))
    resumen = api.sincronizar(tmp_path / "b", almacen=bucket)
    assert resumen["recuperados"] == 2 and resumen["nuevos"] == 1
    payload = load_discord_raw_stream(str(tmp_path / "b"))
    assert len(payload.interacciones) == 3 and payload.interacciones[0].texto == "llegó después"
