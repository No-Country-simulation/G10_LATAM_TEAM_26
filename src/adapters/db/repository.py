"""
CommunityLab AI - Repositorio de Base de Datos
Conexión de alta disponibilidad a OCI Autonomous Database con autoreconexión y prevención de DPY-4011.
"""
import os
import bcrypt
from datetime import datetime, timezone
from typing import List, Optional, Set
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import oracledb

from src.adapters.db.models import Base, User, CommunityMessage, MarketingAsset
from src.domain.schemas import RawMessageInteraction
from src.utils.logger import setup_logger

logger = setup_logger("db_repository")

DB_USER = os.getenv("OCI_DB_USER", "ADMIN")
DB_PASSWORD = os.getenv("OCI_DB_PASSWORD", "")
WALLET_PATH = os.getenv("OCI_DB_WALLET_PATH", "/app/data/wallet/Wallet_communitylabdb")
WALLET_PASSWORD = os.getenv("OCI_DB_WALLET_PASSWORD", "")
TNS_NAME = os.getenv("OCI_DB_TNS_NAME", "communitylabdb_low")


def get_oracle_connection():
    """Genera una nueva conexión autenticada por mTLS a Oracle Cloud."""
    return oracledb.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=TNS_NAME,
        config_dir=WALLET_PATH,
        wallet_location=WALLET_PATH,
        wallet_password=WALLET_PASSWORD,
        expire_time=2  # Keep-alive cada 2 minutos a nivel TCP
    )


# Detección y configuración del motor SQLAlchemy
if DB_PASSWORD and (os.path.exists(WALLET_PATH) or os.path.exists("data/wallet/Wallet_communitylabdb")):
    logger.info("Configurando conexión a OCI Autonomous Database (Santiago Always Free)...")
    DATABASE_URL = "oracle+oracledb://"
    engine = create_engine(
        DATABASE_URL,
        creator=get_oracle_connection,
        pool_pre_ping=True,       # Verifica salud del socket antes de cada query (evita DPY-4011)
        pool_recycle=60,          # Recicla la conexión cada 60s
        pool_size=5,
        max_overflow=10
    )
else:
    logger.info("Usando SQLite local de contingencia...")
    DATABASE_URL = "sqlite:///data/communitylab.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Inicializa tablas y usuario admin en OCI."""
    try:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            admin = db.query(User).filter(User.username == "admin").first()
            if not admin:
                admin_pass = os.getenv("ADMIN_PASSWORD", "CommunityLab2026!")
                salt = bcrypt.gensalt()
                hashed = bcrypt.hashpw(admin_pass.encode('utf-8'), salt).decode('utf-8')
                new_admin = User(
                    username="admin",
                    password_hash=hashed,
                    email="admin@communitylab.ai",
                    role="ADMIN",
                    is_active=True
                )
                db.add(new_admin)
                db.commit()
                logger.info("Base de datos OCI inicializada con tablas y usuario admin.")
    except Exception as e:
        logger.error(f"Error inicializando BD: {str(e)}")
        raise e


def verify_user(username: str, password: str) -> Optional[User]:
    try:
        with SessionLocal() as db:
            user = db.query(User).filter(User.username == username, User.is_active == True).first()
            if user and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                return user
    except Exception as e:
        logger.error(f"Error verificando usuario: {str(e)}")
    return None


def register_user(username: str, password: str, email: str = "", role: str = "CURATOR") -> Optional[User]:
    try:
        with SessionLocal() as db:
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
            user = User(username=username, password_hash=hashed, email=email, role=role)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
    except Exception as e:
        logger.error(f"Error registrando usuario: {str(e)}")
        return None


def _normalizar_source(source: Optional[str]) -> Optional[List[str]]:
    """Devuelve las variantes equivalentes del source para no perder datos históricos."""
    if not source:
        return None
    s = source.lower()
    if "discord" in s:
        return ["discord", "discord_live"]
    if "fixture" in s or "estandar" in s:
        return ["fixture_estandar", "fixture"]
    if "upload" in s:
        return ["upload_usuario", "upload"]
    return [source]


def get_existing_message_ids(source: Optional[str] = None) -> Set[str]:
    """Obtiene los IDs de mensajes guardados en OCI filtrando por fuente normalizada."""
    try:
        with SessionLocal() as db:
            query = db.query(CommunityMessage.message_id)
            variantes = _normalizar_source(source)
            if variantes:
                query = query.filter(CommunityMessage.source.in_(variantes))
            ids = query.all()
            return {item[0] for item in ids}
    except Exception as e:
        logger.error(f"Error consultando IDs en OCI: {str(e)}")
        return set()


def get_stored_count_by_source(source: Optional[str] = None) -> int:
    """Cuenta los mensajes guardados en Oracle para la fuente activa."""
    try:
        with SessionLocal() as db:
            query = db.query(CommunityMessage)
            variantes = _normalizar_source(source)
            if variantes:
                query = query.filter(CommunityMessage.source.in_(variantes))
            return query.count()
    except Exception as e:
        logger.error(f"Error contando mensajes en OCI: {str(e)}")
        return 0


def filter_unprocessed_interactions(interactions: List[RawMessageInteraction], source: Optional[str] = None) -> List[RawMessageInteraction]:
    existing_ids = get_existing_message_ids(source=source)
    nuevos = [m for m in interactions if m.message_id not in existing_ids]
    logger.info(f"Deduplicación OCI ({source or 'global'}): {len(interactions)} recibidos, {len(nuevos)} nuevos.")
    return nuevos


def save_processed_messages(processed_items: list, source: str = "discord_live"):
    """Guarda los mensajes en Oracle Cloud asignando su fuente de origen respectiva."""
    if not processed_items:
        return

    try:
        with SessionLocal() as db:
            guardados = 0
            for proc, assets in processed_items:
                existe = db.query(CommunityMessage).filter(CommunityMessage.message_id == proc.message_id).first()
                if not existe:
                    tipo_val = proc.opportunity.type.value if hasattr(proc.opportunity.type, "value") else str(proc.opportunity.type)
                    msg_record = CommunityMessage(
                        message_id=proc.message_id,
                        source=source,
                        channel=proc.channel,
                        author_raw=proc.autor_anonimizado,
                        author_anon=proc.autor_anonimizado,
                        raw_text=proc.texto_limpio,
                        clean_text=proc.texto_limpio,
                        processed=True,
                        processed_at=datetime.now(timezone.utc),
                        sentiment=proc.analysis.sentiment,
                        topics=",".join(proc.analysis.topics),
                        opportunity_score=proc.opportunity.opportunity_score,
                        opportunity_type=tipo_val
                    )
                    db.add(msg_record)
                    try:
                        db.flush()
                        guardados += 1
                    except Exception:
                        db.rollback()
                        continue

            db.commit()
            logger.info(f"✅ ¡ÉXITO! {guardados} mensajes ({source}) insertados y confirmados en Oracle Cloud.")
    except Exception as e:
        logger.error(f"Fallo al guardar mensajes en OCI: {str(e)}")

def get_high_value_opportunities(min_score: float = 0.70, source: Optional[str] = None) -> List[CommunityMessage]:
    """Recupera desde Oracle Cloud las oportunidades con Score >= min_score, aisladas por fuente activa."""
    try:
        with SessionLocal() as db:
            query = db.query(CommunityMessage).filter(CommunityMessage.opportunity_score >= min_score)
            
            # Filtrar por fuente si se especifica (aislamiento estricto)
            variantes = _normalizar_source(source)
            if variantes:
                query = query.filter(CommunityMessage.source.in_(variantes))

            return query.order_by(CommunityMessage.opportunity_score.desc()).all()
    except Exception as e:
        logger.error(f"Error consultando oportunidades en OCI ({source}): {str(e)}")
        return []

def get_saved_marketing_assets() -> List[MarketingAsset]:
    """Recupera desde Oracle Cloud todos los activos de marketing registrados."""
    try:
        with SessionLocal() as db:
            return db.query(MarketingAsset).order_by(MarketingAsset.id.desc()).all()
    except Exception as e:
        logger.error(f"Error consultando activos en OCI: {str(e)}")
        return []

def get_community_analytics_summary() -> dict:
    """
    Calcula métricas agregadas directamente desde Oracle Cloud:
    distribución de oportunidades, sentimientos, canales y estado de activos.
    """
    try:
        with SessionLocal() as db:
            mensajes = db.query(CommunityMessage).all()
            total = len(mensajes)
            
            if total == 0:
                return {
                    "total_oci": 0,
                    "tipos": {},
                    "sentimientos": {},
                    "canales": {},
                    "con_post": 0,
                    "sin_post": 0
                }

            tipos = {}
            sentimientos = {}
            canales = {}
            con_post = 0

            for m in mensajes:
                # Tipos de oportunidad
                t = m.opportunity_type or "NONE"
                tipos[t] = tipos.get(t, 0) + 1

                # Sentimiento
                s = m.sentiment or "neutral"
                sentimientos[s] = sentimientos.get(s, 0) + 1

                # Canales
                c = f"#{m.channel}" if m.channel else "#general"
                canales[c] = canales.get(c, 0) + 1

                # Relación con activos de marketing
                if len(m.assets) > 0:
                    con_post += 1

            return {
                "total_oci": total,
                "tipos": tipos,
                "sentimientos": sentimientos,
                "canales": canales,
                "con_post": con_post,
                "sin_post": total - con_post
            }
    except Exception as e:
        logger.error(f"Error calculando analíticas en OCI: {str(e)}")
        return {
            "total_oci": 0,
            "tipos": {},
            "sentimientos": {},
            "canales": {},
            "con_post": 0,
            "sin_post": 0
        }