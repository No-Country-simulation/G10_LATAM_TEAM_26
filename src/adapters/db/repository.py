"""
CommunityLab AI - Repositorio de la base de la comunidad
OCI Autonomous Database (conexión mTLS con wallet) si hay credenciales; si no, SQLite local de contingencia.
Usuarios del panel (contraseñas con bcrypt), deduplicación de mensajes ya procesados por comunidad, y registro de
mensajes analizados y activos de marketing. Basado en la integración de Álvaro con Oracle Cloud.

La wallet nunca va al repositorio: se copia a OCI_DB_WALLET_PATH (data/wallet/ está en .gitignore).
"""
import os
from collections import Counter
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import bcrypt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src import config
from src.adapters.db.models import Base, CommunityMessage, MarketingAsset, User
from src.utils.logger import setup_logger

logger = setup_logger("db_repository")

def _ruta(valor: str) -> str:
    """Rutas del .env relativas a la raíz del proyecto (sirven igual en local y en Docker, donde la raíz es /app)."""
    ruta = Path(os.path.expanduser(valor))
    return str(ruta if ruta.is_absolute() else config.RAIZ / ruta)


DB_USER = os.getenv("OCI_DB_USER", "ADMIN")
DB_PASSWORD = os.getenv("OCI_DB_PASSWORD", "")
WALLET_PATH = _ruta(os.getenv("OCI_DB_WALLET_PATH", "data/wallet/Wallet_communitylabdb"))
WALLET_PASSWORD = os.getenv("OCI_DB_WALLET_PASSWORD", "")
TNS_NAME = os.getenv("OCI_DB_TNS_NAME", "communitylabdb_low")
SQLITE_PATH = os.getenv("DB_SQLITE_PATH", str(config.RAIZ / "data" / "communitylab.db"))


def usa_oracle() -> bool:
    return bool(DB_PASSWORD) and Path(WALLET_PATH).exists()


@lru_cache(maxsize=1)
def _motor():
    """El motor se crea al primer uso (no al importar): la CLI y los tests no abren conexiones."""
    if usa_oracle():
        import oracledb

        def conectar():
            return oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=TNS_NAME, config_dir=WALLET_PATH,
                                    wallet_location=WALLET_PATH, wallet_password=WALLET_PASSWORD, expire_time=2)

        logger.info("Base de datos: OCI Autonomous Database (wallet mTLS)")
        return create_engine("oracle+oracledb://", creator=conectar, pool_pre_ping=True, pool_recycle=60,
                             pool_size=5, max_overflow=10)
    Path(SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Base de datos: SQLite local ({SQLITE_PATH})")
    return create_engine(f"sqlite:///{SQLITE_PATH}", connect_args={"check_same_thread": False})


def nombre_motor() -> str:
    return "OCI Autonomous Database" if usa_oracle() else "SQLite local"


@contextmanager
def sesion():
    with sessionmaker(bind=_motor(), autoflush=False, expire_on_commit=False)() as s:
        yield s


# ─── Usuarios ─────────────────────────────────────────────────────────────────

def _hash(clave: str) -> str:
    return bcrypt.hashpw(clave.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def init_db() -> None:
    """Crea las tablas si no existen y, si ADMIN_PASSWORD está definido, el usuario administrador inicial."""
    Base.metadata.create_all(bind=_motor())
    admin_user, admin_pass = os.getenv("ADMIN_USER", "admin"), os.getenv("ADMIN_PASSWORD", "")
    if not admin_pass:
        return
    with sesion() as s:
        if not s.query(User).filter(User.username == admin_user).first():
            s.add(User(username=admin_user, password_hash=_hash(admin_pass), role="ADMIN", is_active=True))
            s.commit()
            logger.info(f"Usuario administrador '{admin_user}' creado")


def verify_user(username: str, password: str) -> Optional[User]:
    try:
        with sesion() as s:
            usuario = s.query(User).filter(User.username == username, User.is_active.is_(True)).first()
            if usuario and bcrypt.checkpw(password.encode("utf-8"), usuario.password_hash.encode("utf-8")):
                return usuario
    except Exception as error:
        logger.error(f"No se pudo verificar el usuario ({type(error).__name__}: {error})")
    return None


def register_user(username: str, password: str, email: str = "", role: str = "CURATOR") -> Optional[User]:
    try:
        with sesion() as s:
            usuario = User(username=username, password_hash=_hash(password), email=email or None, role=role)
            s.add(usuario)
            s.commit()
            return usuario
    except Exception as error:
        logger.error(f"No se pudo registrar el usuario ({type(error).__name__}: {error})")
        return None


# ─── Mensajes: deduplicación y registro ──────────────────────────────────────

def _clave(comunidad: str, message_id: str) -> str:
    return f"{comunidad}:{message_id}"[:100]


def ids_procesados(comunidad: str) -> Set[str]:
    """message_id (sin prefijo) de los mensajes de esa comunidad ya guardados."""
    prefijo = f"{comunidad}:"
    with sesion() as s:
        filas = s.query(CommunityMessage.message_id).filter(CommunityMessage.message_id.startswith(prefijo)).all()
    return {f[0][len(prefijo):] for f in filas}


def separar_nuevos(interacciones: List[Dict[str, Any]], comunidad: str) -> Tuple[List[Dict[str, Any]], int]:
    """(mensajes nuevos, cantidad de repetidos) según lo ya procesado para la comunidad. Si la base no responde,
    no filtra nada: es preferible reprocesar a perder mensajes."""
    try:
        vistos = ids_procesados(comunidad)
    except Exception as error:
        logger.error(f"No se pudo consultar la base para deduplicar ({type(error).__name__}); se procesa todo")
        return interacciones, 0
    nuevos = [m for m in interacciones if m["message_id"] not in vistos]
    return nuevos, len(interacciones) - len(nuevos)


def guardar_mensajes(procesados: Iterable[Dict[str, Any]], textos: Dict[str, Dict[str, Any]], comunidad: str) -> int:
    """Registra los mensajes analizados (filas del Formato P) que todavía no estén en la base. Devuelve cuántos."""
    guardados = 0
    with sesion() as s:
        existentes = {f[0] for f in s.query(CommunityMessage.message_id)
                      .filter(CommunityMessage.message_id.startswith(f"{comunidad}:")).all()}
        for p in procesados:
            mid = p["tracking"]["message_id"]
            clave = _clave(comunidad, mid)
            if clave in existentes:
                continue
            original = textos.get(mid, {})
            autor = (original.get("autor") or "Miembro")[:100]
            texto = original.get("texto", "")
            s.add(CommunityMessage(
                message_id=clave, source=(p["tracking"].get("source") or "discord")[:50],
                channel=(p["tracking"].get("channel") or "sin-canal")[:100], author_raw=autor, author_anon=autor,
                raw_text=texto, clean_text=texto, processed=True, sentiment=p["analysis"]["sentiment"],
                topics=",".join(p["analysis"]["topics"])[:255], opportunity_score=p["opportunity"]["opportunity_score"],
                opportunity_type=p["opportunity"]["type"]))
            existentes.add(clave)
            guardados += 1
        s.commit()
    logger.info(f"{guardados} mensajes de '{comunidad}' guardados en {nombre_motor()}")
    return guardados


# ─── Activos de marketing ────────────────────────────────────────────────────

def _texto_activo(activo: Dict[str, Any]) -> Tuple[str, str]:
    c = activo["contenido"]
    if activo["formato"] == "post_linkedin":
        return c.get("titulo", ""), c.get("copy", "")
    if activo["formato"] == "destaque_newsletter":
        return c.get("titular", ""), c.get("resumen", "")
    return c.get("tema", ""), c.get("cuerpo", "")


def guardar_activos(paquete: Dict[str, Any], comunidad: str, usuario: Optional[str] = None) -> int:
    """Registra o actualiza los activos del paquete con su estado de curaduría y su ruta en el bucket."""
    with sesion() as s:
        aprobador = s.query(User).filter(User.username == usuario).first() if usuario else None
        for activo in paquete["activos"]:
            post_id = f"{paquete['paquete_id']}/{activo['activo_id']}"[:50]
            titulo, cuerpo = _texto_activo(activo)
            registro = s.query(MarketingAsset).filter(MarketingAsset.post_id == post_id).first() or MarketingAsset(
                post_id=post_id)
            mensaje = s.query(CommunityMessage).filter(
                CommunityMessage.message_id == _clave(comunidad, activo["origen"]["message_id"])).first()
            registro.community_message_id = mensaje.id if mensaje else None
            registro.origin_message_id = activo["origen"]["message_id"]
            registro.asset_type = activo["formato"]
            registro.title = (titulo or activo["activo_id"])[:255]
            registro.copy = cuerpo
            registro.status = activo["estado_curaduria"]
            registro.oci_object_path = paquete["almacenamiento_oci"]["ruta_objeto"][:255]
            if aprobador and activo["estado_curaduria"] in ("aprobado", "publicado"):
                registro.approved_by_user_id = aprobador.id
            s.add(registro)
        s.commit()
    return len(paquete["activos"])


# ─── Analítica histórica ─────────────────────────────────────────────────────

def resumen_historico() -> Dict[str, Any]:
    """Totales de todo lo guardado: mensajes por tipo, sentimiento y canal, y activos por estado."""
    with sesion() as s:
        mensajes = s.query(CommunityMessage.opportunity_type, CommunityMessage.sentiment,
                           CommunityMessage.channel).all()
        activos = s.query(MarketingAsset.status).all()
    return {
        "mensajes": len(mensajes),
        "tipos": dict(Counter(t or "NONE" for t, _, _ in mensajes)),
        "sentimientos": dict(Counter(se or "neutral" for _, se, _ in mensajes)),
        "canales": dict(Counter(c for _, _, c in mensajes).most_common(8)),
        "activos": dict(Counter(st for (st,) in activos)),
    }
