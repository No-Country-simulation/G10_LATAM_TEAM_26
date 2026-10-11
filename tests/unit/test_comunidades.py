"""
CommunityLab AI - Unit Tests
Comunidades de Discord: alta con token y servidor, el token nunca llega al panel, y cada una lee y guarda aparte.
"""
import pytest

from src.adapters.ingestion import discord_comunidades as comunidades


@pytest.fixture
def registro(tmp_path, monkeypatch):
    monkeypatch.setattr(comunidades, "CARPETA_COMUNIDADES", tmp_path)
    monkeypatch.setattr(comunidades, "ARCHIVO", tmp_path / "comunidades.json")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "token-principal-1234567890")
    return comunidades


def test_la_principal_viene_del_env_y_no_expone_el_token(registro):
    principal = registro.publica(registro.obtener(None))
    assert principal["id"] == "principal" and principal["configurada"] and principal["token_final"] == "…7890"
    assert "token" not in principal


def test_agregar_listar_y_quitar(registro):
    nueva = registro.agregar("Comunidad Python Perú", "otro-token-abcdefgh", "555", "Python Perú")
    assert nueva["origen"] == "Discord_Comunidad_Python_Peru" and nueva["prefijo"].startswith("discordcom-")
    assert nueva["carpeta"] != registro.obtener("principal")["carpeta"]  # cada comunidad guarda aparte
    assert [c["id"] for c in registro.listar()] == ["principal", nueva["id"]]
    assert registro.obtener(nueva["id"])["servidor_id"] == "555"
    with pytest.raises(ValueError):
        registro.agregar("comunidad python perú", "x" * 12, "1", "x")  # nombre repetido
    assert registro.eliminar(nueva["id"]) and [c["id"] for c in registro.listar()] == ["principal"]
    with pytest.raises(KeyError):
        registro.obtener(nueva["id"])
