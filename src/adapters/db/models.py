"""
CommunityLab AI - Modelos relacionales (SQLAlchemy)
Tablas de la base de la comunidad: usuarios del panel, mensajes procesados y activos de marketing.
Mismas tablas y columnas que la base OCI Autonomous Database de Álvaro; las claves usan Identity, que Oracle crea
como columna autoincremental nativa y SQLite (la base local de contingencia) como INTEGER PRIMARY KEY.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Identity, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _ahora():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    role = Column(String(20), default="CURATOR", nullable=False)  # ADMIN | CURATOR | VIEWER
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_ahora)

    approved_assets = relationship("MarketingAsset", back_populates="approver")


class CommunityMessage(Base):
    """Un mensaje ya analizado. message_id guarda '<comunidad>:<message_id>': el mismo id (p. ej. MSG-0001) puede
    repetirse en lotes de comunidades distintas, y la tabla exige que sea único."""
    __tablename__ = "community_messages"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    message_id = Column(String(100), unique=True, nullable=False, index=True)
    source = Column(String(50), nullable=False, default="discord")
    channel = Column(String(100), nullable=False)
    author_raw = Column(String(100), nullable=False)
    author_anon = Column(String(100), nullable=False)
    raw_text = Column(Text, nullable=False)
    clean_text = Column(Text, nullable=False)

    processed = Column(Boolean, default=True, nullable=False, index=True)
    processed_at = Column(DateTime, default=_ahora)
    sentiment = Column(String(50), nullable=True)
    topics = Column(String(255), nullable=True)
    opportunity_score = Column(Float, nullable=True)
    opportunity_type = Column(String(50), nullable=True)

    assets = relationship("MarketingAsset", back_populates="origin_message")


class MarketingAsset(Base):
    """Un activo del paquete (post, newsletter o FAQ) con su estado de curaduría y su ruta en el bucket."""
    __tablename__ = "marketing_assets"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    post_id = Column(String(50), unique=True, nullable=False, index=True)  # '<paquete_id>/<activo_id>'
    community_message_id = Column(Integer, ForeignKey("community_messages.id"), nullable=True)
    origin_message_id = Column(String(100), nullable=False, index=True)
    asset_type = Column(String(30), nullable=False)
    title = Column(String(255), nullable=False)
    copy = Column(Text, nullable=False)
    status = Column(String(30), default="borrador", nullable=False)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    oci_object_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=_ahora)

    origin_message = relationship("CommunityMessage", back_populates="assets")
    approver = relationship("User", back_populates="approved_assets")
