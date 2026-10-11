"""
CommunityLab AI - API web (FastAPI)
Expone el mismo motor que usa el panel de Streamlit para el front en React (frontend/). Si existe frontend/dist,
también sirve el front compilado: una sola app y un solo puerto.

  uvicorn src.api.app:app --port 8000
"""
import io
import json
import os
import secrets
import threading
import time
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, Header, HTTPException  # noqa: E402
from fastapi.responses import FileResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src import config  # noqa: E402
from src.adapters.cloud.oci_storage import ObjectStorageAdapter  # noqa: E402
from src.adapters.db import repository  # noqa: E402
from src.adapters.ingestion import discord_comunidades as comunidades  # noqa: E402
from src.adapters.ingestion.discord_api import DiscordAPI  # noqa: E402
from src.adapters.ingestion.loaders import (load_discord_raw_stream, load_fixture_data,  # noqa: E402
                                            load_uploaded_json_file)
from src.api.espacio import Espacio  # noqa: E402
from src.api import publicaciones as pub  # noqa: E402
from src.core.agents.strategist import regenerar_pieza  # noqa: E402
from src.core.media_kit import media_kit  # noqa: E402
from src.utils.logger import setup_logger  # noqa: E402

logger = setup_logger("api")
app = FastAPI(title="CommunityLab AI", docs_url="/api/docs", openapi_url="/api/openapi.json")

SESIONES: Dict[str, Espacio] = {}
ERROR_BASE = ""
try:
    repository.init_db()
except Exception as error:  # el panel funciona igual; la base se reporta como no disponible
    ERROR_BASE = f"{type(error).__name__}: {str(error)[:160]}"


@lru_cache(maxsize=1)
def almacenamiento() -> ObjectStorageAdapter:
    return ObjectStorageAdapter()


_discord: Dict[str, Dict[str, Any]] = {}  # estado de la última lectura de cada comunidad
_bloqueo_discord = threading.Lock()  # dos sesiones a la vez no deben agregar lo mismo dos veces


def _estado_discord(comunidad_id: str) -> Dict[str, Any]:
    return _discord.setdefault(comunidad_id, {"momento": 0.0, "nuevos": 0, "error": ""})


def _explicar_error_discord(error: Exception) -> str:
    """Motivo legible para el curador (sin URLs ni trazas técnicas)."""
    codigo = getattr(getattr(error, "response", None), "status_code", None)
    if codigo == 401:
        return "el token ya no es válido o fue revocado"
    if codigo == 403:
        return "la aplicación no tiene permiso para leer esos canales"
    if codigo == 429:
        return "Discord limitó las consultas por un momento; intenta en un minuto"
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return "no hubo conexión con Discord"
    return f"error inesperado ({type(error).__name__})"


def sincronizar_discord(comunidad: Dict[str, Any], refrescar: bool = False) -> str:
    """Trae de Discord solo lo nuevo de esa comunidad desde la última lectura, a lo más una vez por minuto (salvo
    que se pida refrescar). Devuelve el error, si hubo; lo leído queda en la carpeta de la comunidad y en raw/."""
    estado = _estado_discord(comunidad["id"])
    with _bloqueo_discord:
        if refrescar or time.time() - estado["momento"] > 60:
            try:
                oci = almacenamiento()
                resumen = DiscordAPI(comunidad["token"], servidor_id=comunidad.get("servidor_id")).sincronizar(
                    comunidad["carpeta"], almacen=oci if oci.conectado else None, prefijo=comunidad["prefijo"])
                estado.update(nuevos=resumen["nuevos"], error="")
            except Exception as error:
                estado.update(nuevos=0, error=_explicar_error_discord(error))
            estado["momento"] = time.time()
    return estado["error"]


# ─── Sesión ──────────────────────────────────────────────────────────────────

def espacio(authorization: str = Header(default="")) -> Espacio:
    token = authorization.removeprefix("Bearer ").strip()
    if token not in SESIONES:
        raise HTTPException(401, "Tu sesión terminó. Vuelve a ingresar.")
    return SESIONES[token]


def autenticar(usuario: str, clave: str):
    """Primero contra la base y, como respaldo, contra ADMIN_USER / ADMIN_PASSWORD del .env (igual que el panel)."""
    registro = repository.verify_user(usuario, clave)
    if registro:
        return registro.username, registro.role
    admin_user, admin_pass = os.getenv("ADMIN_USER", "admin"), os.getenv("ADMIN_PASSWORD", "")
    if admin_pass and usuario == admin_user and clave == admin_pass:
        return usuario, "ADMIN"
    return None


class Credenciales(BaseModel):
    usuario: str
    clave: str


@app.post("/api/login")
def login(datos: Credenciales):
    resultado = autenticar(datos.usuario.strip(), datos.clave)
    if not resultado:
        raise HTTPException(401, "Usuario o contraseña incorrectos.")
    token = secrets.token_urlsafe(32)
    SESIONES[token] = Espacio(*resultado)
    return {"token": token, "usuario": resultado[0], "rol": resultado[1]}


@app.post("/api/logout")
def logout(authorization: str = Header(default="")):
    SESIONES.pop(authorization.removeprefix("Bearer ").strip(), None)
    return {"ok": True}


@app.get("/api/sistema")
def sistema(e: Espacio = Depends(espacio)):
    return {
        "usuario": e.usuario, "rol": e.rol,
        "base": repository.nombre_motor(), "error_base": ERROR_BASE,
        "oci_conectado": almacenamiento().conectado, "bucket": almacenamiento().bucket_name,
        "discord_configurado": any(c["configurada"] for c in map(comunidades.publica, comunidades.listar())),
        "tamano_lote": config.TAMANO_LOTE, "max_concurrencia": config.MAX_CONCURRENCIA,
        "imagenes": config.GENERAR_IMAGENES, "umbrales": config.UMBRALES_POR_TIPO,
    }


class NuevoUsuario(BaseModel):
    usuario: str
    clave: str
    rol: str = "CURATOR"


@app.post("/api/usuarios")
def crear_usuario(datos: NuevoUsuario, e: Espacio = Depends(espacio)):
    if e.rol != "ADMIN":
        raise HTTPException(403, "Solo un administrador puede crear usuarios.")
    if datos.rol not in ("CURATOR", "VIEWER", "ADMIN") or not (datos.usuario.strip() and datos.clave):
        raise HTTPException(400, "Completa el usuario, la contraseña y un rol válido.")
    if not repository.register_user(datos.usuario.strip(), datos.clave, role=datos.rol):
        raise HTTPException(409, f"No se pudo crear «{datos.usuario}». ¿Ya existe?")
    return {"usuario": datos.usuario.strip(), "rol": datos.rol}


# ─── Origen de datos ─────────────────────────────────────────────────────────

def _resumen_dataset(e: Espacio, aviso: str = "") -> Dict[str, Any]:
    d = e.dataset
    if not d:  # p. ej., una comunidad de Discord sin mensajes o con el token revocado: se queda en esa fuente
        return {"fuente": e.fuente, "total": 0, "interacciones": [], "aviso": aviso, "analizados": [],
                "comunidad_discord": e.discord_comunidad if e.fuente == "discord" else None}
    tipos = Counter(m.tipo_declarado or "otro" for m in d.interacciones)
    estado = _estado_discord(e.discord_comunidad) if e.fuente == "discord" else None
    try:  # mensajes de este lote que ya se analizaron con IA en sesiones anteriores (están en la base)
        en_base = repository.ids_procesados(d.origen_comunidad)
        analizados = sorted(m.message_id for m in d.interacciones if m.message_id in en_base)
    except Exception:
        analizados = []
    return {
        "fuente": e.fuente, "archivo": e.nombre_archivo, "aviso": aviso,
        "consultado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(estado["momento"]))
        if estado and estado["momento"] else None,
        "nuevos": estado["nuevos"] if estado else None,
        "comunidad_discord": e.discord_comunidad if e.fuente == "discord" else None,
        "origen_comunidad": d.origen_comunidad, "periodo_referencia": d.periodo_referencia,
        "total": len(d.interacciones), "tipos_declarados": dict(tipos), "analizados": analizados,
        "interacciones": [m.model_dump() for m in d.interacciones],
    }


@app.get("/api/dataset")
def dataset_actual(e: Espacio = Depends(espacio)):
    return _resumen_dataset(e)


class Fuente(BaseModel):
    fuente: str
    refrescar: bool = False
    comunidad: Optional[str] = None  # comunidad de Discord; por defecto, la principal


@app.post("/api/dataset/fuente")
def elegir_fuente(datos: Fuente, e: Espacio = Depends(espacio)):
    aviso = ""
    if datos.fuente == "discord":
        try:
            comunidad = comunidades.obtener(datos.comunidad)
        except KeyError:
            raise HTTPException(404, "Esa comunidad de Discord ya no existe.")
        e.discord_comunidad = comunidad["id"]
        error = sincronizar_discord(comunidad, datos.refrescar) if comunidades.publica(comunidad)["configurada"] else ""
        e.dataset = load_discord_raw_stream(str(comunidad["raw_dir"]), origen=comunidad["origen"])
        if error:
            aviso = f"No se pudo leer Discord: {error}. Se muestran los mensajes ya leídos de esta comunidad."
        if e.dataset is None and not error:
            aviso = "Esta comunidad todavía no tiene mensajes en sus canales."
    else:
        e.dataset = load_fixture_data()
    e.fuente, e.nombre_archivo = datos.fuente, None
    return _resumen_dataset(e, aviso)


# ─── Comunidades de Discord ──────────────────────────────────────────────────

@app.get("/api/discord/comunidades")
def listar_comunidades(e: Espacio = Depends(espacio)):
    return [comunidades.publica(c) for c in comunidades.listar()]


class TokenDiscord(BaseModel):
    token: str


def _solo_admin(e: Espacio) -> None:
    if e.rol != "ADMIN":
        raise HTTPException(403, "Solo un administrador puede agregar o quitar comunidades.")


@app.post("/api/discord/verificar")
def verificar_token(datos: TokenDiscord, e: Espacio = Depends(espacio)):
    """Comprueba el token y devuelve los servidores donde está la aplicación, para elegir uno."""
    _solo_admin(e)
    try:
        identidad = DiscordAPI(datos.token).identidad()
    except PermissionError as error:
        raise HTTPException(400, str(error))
    except Exception as error:
        raise HTTPException(502, f"Discord no respondió ({type(error).__name__}).")
    if not identidad["servidores"]:
        raise HTTPException(400, "El token es válido, pero la aplicación no está en ningún servidor. Invítala primero.")
    return identidad


class NuevaComunidad(BaseModel):
    nombre: str
    token: str
    servidor_id: str


@app.post("/api/discord/comunidades")
def agregar_comunidad(datos: NuevaComunidad, e: Espacio = Depends(espacio)):
    _solo_admin(e)
    if not datos.nombre.strip():
        raise HTTPException(400, "Ponle un nombre a la comunidad.")
    identidad = verificar_token(TokenDiscord(token=datos.token), e)
    servidor = next((s for s in identidad["servidores"] if s["id"] == datos.servidor_id), None)
    if not servidor:
        raise HTTPException(400, "La aplicación no tiene acceso a ese servidor.")
    try:
        nueva = comunidades.agregar(datos.nombre, datos.token, servidor["id"], servidor["nombre"])
    except ValueError as error:
        raise HTTPException(409, str(error))
    return comunidades.publica(nueva)


@app.delete("/api/discord/comunidades/{comunidad_id}")
def quitar_comunidad(comunidad_id: str, e: Espacio = Depends(espacio)):
    _solo_admin(e)
    if comunidad_id == comunidades.PRINCIPAL:
        raise HTTPException(400, "La comunidad principal se configura en el .env del servidor.")
    if not comunidades.eliminar(comunidad_id):
        raise HTTPException(404, "Esa comunidad ya no existe.")
    return {"ok": True}


class Archivo(BaseModel):
    nombre: str
    contenido: str


@app.post("/api/dataset/archivo")
def subir_archivo(datos: Archivo, e: Espacio = Depends(espacio)):
    try:
        e.dataset = load_uploaded_json_file(io.StringIO(datos.contenido))
    except ValueError as error:
        raise HTTPException(400, str(error))
    e.fuente, e.nombre_archivo = "archivo", datos.nombre
    return _resumen_dataset(e)


# ─── Análisis ────────────────────────────────────────────────────────────────

class PedidoAnalisis(BaseModel):
    cantidad: int
    simulado: bool = False
    omitir_repetidos: bool = True


@app.post("/api/analisis")
def analizar(datos: PedidoAnalisis, e: Espacio = Depends(espacio)):
    try:
        return e.analizar(max(1, datos.cantidad), datos.simulado, datos.omitir_repetidos)
    except ValueError as error:
        raise HTTPException(400, str(error))


@app.get("/api/analisis")
def estado_analisis(e: Espacio = Depends(espacio)):
    return e.estado()


@app.get("/api/resumen")
def resumen(e: Espacio = Depends(espacio)):
    """Métricas de la pestaña Resumen: todo lo analizado y curado que está en la base."""
    try:
        datos = repository.resumen_panel(config.UMBRALES_POR_TIPO)
    except Exception as error:
        return {"base": repository.nombre_motor(), "mensajes": 0, "error": type(error).__name__}
    ultima = datos["ultima_actividad"]
    return {"base": repository.nombre_motor(), **datos, "ultima_actividad": ultima.isoformat() if ultima else None}


@app.get("/api/historico")
def historico(e: Espacio = Depends(espacio)):
    try:
        return {"base": repository.nombre_motor(), **repository.resumen_historico()}
    except Exception as error:
        return {"base": repository.nombre_motor(), "mensajes": 0, "error": type(error).__name__}


# ─── Curaduría ───────────────────────────────────────────────────────────────

def _paquete(e: Espacio) -> Dict[str, Any]:
    if not e.paquete:
        raise HTTPException(404, "Todavía no hay un paquete. Analiza un lote primero.")
    return e.paquete


def _activo(e: Espacio, activo_id: str) -> Dict[str, Any]:
    for activo in list(_paquete(e)["activos"]):
        if activo["activo_id"] == activo_id:
            return activo
    raise HTTPException(404, f"No existe el activo {activo_id}.")


@app.get("/api/paquete")
def paquete(e: Espacio = Depends(espacio)):
    p = _paquete(e)
    return {**p, "activos": list(p["activos"])}


class Edicion(BaseModel):
    contenido: Optional[Dict[str, Any]] = None
    estado: Optional[str] = None


@app.patch("/api/activos/{activo_id}")
def editar_activo(activo_id: str, datos: Edicion, e: Espacio = Depends(espacio)):
    """Guarda la edición. Con `estado` aprueba, descarta o devuelve a borrador; editar un aprobado lo devuelve a
    borrador (la misma regla del Content Studio)."""
    activo = _activo(e, activo_id)
    cambio = bool(datos.contenido) and any(activo["contenido"].get(k) != v for k, v in datos.contenido.items())
    if datos.contenido:
        activo["contenido"].update(datos.contenido)
    if datos.estado:
        if datos.estado not in ("borrador", "aprobado", "descartado"):
            raise HTTPException(400, "Estado de curaduría no válido.")
        activo["estado_curaduria"] = datos.estado
    elif cambio and activo["estado_curaduria"] == "aprobado":
        activo["estado_curaduria"] = "borrador"
    return activo


class Indicaciones(BaseModel):
    indicaciones: str = ""


@app.post("/api/activos/{activo_id}/regenerar")
def regenerar(activo_id: str, datos: Indicaciones, e: Espacio = Depends(espacio)):
    activo = _activo(e, activo_id)
    nuevo = regenerar_pieza(activo, datos.indicaciones, e.simulado)
    if not nuevo:
        raise HTTPException(502, "No se pudo regenerar el borrador. Revisa la cuota de la IA.")
    activo["contenido"].update(nuevo)
    activo["estado_curaduria"] = "borrador"
    return activo


class PedidoImagen(BaseModel):
    prompt: Optional[str] = None  # si el curador lo cambia; si no, se usa el que propuso la IA


@app.post("/api/activos/{activo_id}/imagen")
def otra_imagen(activo_id: str, datos: Optional[PedidoImagen] = None, e: Espacio = Depends(espacio)):
    activo = _activo(e, activo_id)
    if not activo.get("imagen"):
        raise HTTPException(400, "Este activo no lleva imagen.")
    if datos and datos.prompt and datos.prompt.strip():
        activo["imagen"]["prompt"] = datos.prompt.strip()[:400]
    activo["imagen"].update(estado="pendiente", ruta=None, intentos=0)
    e.relanzar_imagenes()
    return activo


@app.get("/api/activos/{activo_id}/imagen")
def ver_imagen(activo_id: str, token: str = ""):
    """El navegador pide la imagen con <img>, que no manda cabeceras: el token viaja en la URL."""
    e = SESIONES.get(token)
    if not e:
        raise HTTPException(401, "Sesión no válida.")
    ruta = (_activo(e, activo_id).get("imagen") or {}).get("ruta")
    if not ruta or not Path(ruta).exists():
        raise HTTPException(404, "La imagen todavía no está lista.")
    return FileResponse(ruta)


@app.get("/api/paquete/media-kit")
def descargar_media_kit(e: Espacio = Depends(espacio)):
    p = _paquete(e)
    return Response(media_kit(p, list(p["activos"])), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{p["paquete_id"]}_media_kit.zip"'})


@app.get("/api/paquete/json")
def descargar_paquete(e: Espacio = Depends(espacio)):
    p = _paquete(e)
    return Response(json.dumps({**p, "activos": list(p["activos"])}, ensure_ascii=False, indent=2),
                    media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{p["paquete_id"]}.json"'})


@app.post("/api/paquete/guardar")
def guardar_paquete(e: Espacio = Depends(espacio)):
    p = _paquete(e)
    if e.generacion and not e.generacion.terminado:
        raise HTTPException(409, "Todavía se están redactando borradores. Espera a que termine para guardar.")
    resultado = almacenamiento().persist_distribution_package(p)
    if e.simulado:
        resultado["activos_en_base"] = "no se registran (modo simulado)"
    else:
        try:
            resultado["activos_en_base"] = repository.guardar_activos(p, e.comunidad or p["origen_comunidad"],
                                                                      e.usuario)
        except Exception as error:
            resultado["activos_en_base"] = f"no se pudieron registrar ({type(error).__name__})"
    e.resultado_oci = resultado
    _guardadas["momento"] = 0.0
    return resultado


# ─── Publicaciones guardadas en OCI ──────────────────────────────────────────

_guardadas: Dict[str, Any] = {"momento": 0.0, "datos": None}


@app.get("/api/publicaciones")
def publicaciones(refrescar: bool = False, e: Espacio = Depends(espacio)):
    """Lo guardado en el bucket (también lo de la versión anterior), a lo más una lectura por minuto."""
    oci = almacenamiento()
    if not oci.conectado:
        return {"conectado": False, "bucket": oci.bucket_name, "publicaciones": []}
    if refrescar or not _guardadas["datos"] or time.time() - _guardadas["momento"] > 60:
        try:
            respuesta = oci.client.list_objects(oci.namespace, oci.bucket_name, prefix=pub.PREFIJO,
                                                fields="name,size,timeCreated", limit=1000)
            objetos = [{"name": o.name, "time_created": o.time_created.isoformat()} for o in respuesta.data.objects]
            leer = lambda nombre: oci.client.get_object(oci.namespace, oci.bucket_name, nombre).data.content  # noqa: E731
            _guardadas["datos"] = {"conectado": True, "bucket": oci.bucket_name, "objetos": len(objetos),
                                   "publicaciones": pub.normalizar(objetos, leer)}
        except Exception as error:
            return {"conectado": True, "bucket": oci.bucket_name, "publicaciones": [],
                    "error": f"{type(error).__name__}: {str(error)[:160]}"}
        _guardadas["momento"] = time.time()
    return {**_guardadas["datos"],
            "consultado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(_guardadas["momento"]))}


@app.get("/api/publicaciones/imagen")
def imagen_guardada(ruta: str, token: str = ""):
    """Imagen de una publicación guardada en el bucket (el <img> no manda cabeceras: el token va en la URL)."""
    if token not in SESIONES:
        raise HTTPException(401, "Sesión no válida.")
    if not pub.ruta_de_imagen_valida(ruta):
        raise HTTPException(400, "Ruta de imagen no válida.")
    oci = almacenamiento()
    if not oci.conectado:
        raise HTTPException(503, "Sin conexión con OCI.")
    try:
        datos = oci.client.get_object(oci.namespace, oci.bucket_name, ruta).data.content
    except Exception:
        raise HTTPException(404, "La imagen no está en el bucket.")
    tipo = pub.EXTENSIONES_IMAGEN[Path(ruta).suffix.lower()]
    return Response(datos, media_type=tipo, headers={"Cache-Control": "private, max-age=3600"})


# ─── Front compilado (npm run build) ─────────────────────────────────────────

DIST = config.RAIZ / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{ruta:path}", include_in_schema=False)
    def front(ruta: str):
        if ruta.startswith("api/"):
            raise HTTPException(404, "No existe esa ruta de la API.")
        archivo = (DIST / ruta).resolve()
        dentro = archivo.is_relative_to(DIST.resolve())  # sin salir de dist/ con rutas tipo ../
        return FileResponse(archivo if ruta and dentro and archivo.is_file() else DIST / "index.html")
