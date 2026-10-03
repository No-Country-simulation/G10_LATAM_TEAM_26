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


def get_existing_message_ids() -> Set[str]:
    """Obtiene los IDs de mensajes guardados en OCI de forma segura."""
    try:
        with SessionLocal() as db:
            ids = db.query(CommunityMessage.message_id).all()
            return {item[0] for item in ids}
    except Exception as e:
        logger.error(f"Error consultando IDs en OCI: {str(e)}")
        return set()


def filter_unprocessed_interactions(interactions: List[RawMessageInteraction]) -> List[RawMessageInteraction]:
    existing_ids = get_existing_message_ids()
    nuevos = [m for m in interactions if m.message_id not in existing_ids]
    logger.info(f"Deduplicación OCI: {len(interactions)} recibidos, {len(nuevos)} nuevos, {len(interactions) - len(nuevos)} ya estaban en Oracle.")
    return nuevos


def save_processed_messages(processed_items: list):
    """Guarda los mensajes en Oracle Cloud de forma resiliente (ignora duplicados ORA-00001)."""
    if not processed_items:
        return

    try:
        with SessionLocal() as db:
            guardados = 0
            for proc, assets in processed_items:
                # Comprobar en base de datos antes de insertar
                existe = db.query(CommunityMessage).filter(CommunityMessage.message_id == proc.message_id).first()
                if not existe:
                    tipo_val = proc.opportunity.type.value if hasattr(proc.opportunity.type, "value") else str(proc.opportunity.type)
                    msg_record = CommunityMessage(
                        message_id=proc.message_id,
                        source="discord",
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
                        db.flush()  # Valida la inserción individual
                        guardados += 1
                    except Exception:
                        db.rollback()  # Si ese ID ya existía por concurrencia, lo salta
                        continue

            db.commit()
            logger.info(f"✅ ¡ÉXITO! {guardados} mensajes nuevos insertados y confirmados en Oracle Cloud.")
    except Exception as e:
        logger.error(f"Fallo al guardar mensajes en OCI: {str(e)}")

def get_high_value_opportunities(min_score: float = 0.70) -> List[CommunityMessage]:
    """Recupera desde Oracle Cloud todas las oportunidades con Score >= min_score."""
    try:
        with SessionLocal() as db:
            return db.query(CommunityMessage)\
                     .filter(CommunityMessage.opportunity_score >= min_score)\
                     .order_by(CommunityMessage.opportunity_score.desc())\
                     .all()
    except Exception as e:
        logger.error(f"Error consultando oportunidades en OCI: {str(e)}")
        return []