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


class _SesionFalsa:
    """Un servidor con #general (2 mensajes), #privado (sin permiso) y un canal de voz."""
    def __init__(self):
        self.pedidos = []

    def get(self, url, params=None, timeout=None, headers=None):
        self.pedidos.append(url)
        assert headers["Authorization"] == "Bot token-falso"
        ruta = url.split("/v10", 1)[1]
        if ruta == "/users/@me/guilds":
            return _Respuesta(200, [{"id": "9", "name": "Comunidad"}])
        if ruta == "/guilds/9/channels":
            return _Respuesta(200, [{"id": "10", "name": "general", "type": 0},
                                    {"id": "11", "name": "privado", "type": 0},
                                    {"id": "12", "name": "Voz", "type": 2}])
        if ruta == "/channels/11/messages":
            return _Respuesta(403, {"code": 50001})
        assert ruta == "/channels/10/messages"
        return _Respuesta(200, [
            {"id": "101", "type": 0, "timestamp": "2026-10-07T19:39:00Z", "content": "hola <@7> <:python:55>",
             "author": {"id": "7", "username": "axel", "global_name": "Axel"},
             "mentions": [{"id": "7", "username": "axel", "global_name": "Axel"}],
             "reactions": [{"emoji": {"name": "🔥"}, "count": 3}]},
            {"id": "100", "type": 7, "timestamp": "2026-10-07T19:00:00Z", "content": "",
             "author": {"id": "8", "username": "nuevo"}},  # aviso de unión al servidor
        ])


def test_api_trae_los_canales_legibles_y_omite_avisos(monkeypatch):
    monkeypatch.delenv("SERVIDORES_OBSERVADOS", raising=False)
    monkeypatch.delenv("CANALES_OBSERVADOS", raising=False)
    sesion = _SesionFalsa()
    registros = DiscordAPI("token-falso", sesion).mensajes_recientes()
    assert [r["id"] for r in registros] == ["101"]
    assert registros[0]["clean_content"] == "hola @Axel :python:"
    assert registros[0]["author"]["display_name"] == "Axel" and registros[0]["channel"]["name"] == "general"
    assert not any("/channels/12/" in u for u in sesion.pedidos)  # los canales de voz no se consultan
    assert payload_desde_discord(registros).interacciones[0].metadata["reacciones"] == 3


def test_api_filtra_canales_y_sin_token_no_consulta(monkeypatch):
    monkeypatch.setenv("CANALES_OBSERVADOS", "privado")
    assert DiscordAPI("token-falso", _SesionFalsa()).mensajes_recientes() == []
    assert DiscordAPI("", _SesionFalsa()).mensajes_recientes() == []
    assert not DiscordAPI("pega-tu-token-aqui").configurado
