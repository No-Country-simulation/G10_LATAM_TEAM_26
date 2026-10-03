"""
CommunityLab AI - Modelos Relacionales de Base de Datos (SQLAlchemy)
100% Compatible con Oracle Database Identity Columns y SQLite.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, Identity
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    # Identity(start=1) genera la columna auto-incremental nativa en Oracle
    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    role = Column(String(20), default="CURATOR", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    approved_assets = relationship("MarketingAsset", back_populates="approver")


class CommunityMessage(Base):
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
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sentiment = Column(String(50), nullable=True)
    topics = Column(String(255), nullable=True)
    opportunity_score = Column(Float, nullable=True)
    opportunity_type = Column(String(50), nullable=True)

    assets = relationship("MarketingAsset", back_populates="origin_message")


class MarketingAsset(Base):
    __tablename__ = "marketing_assets"

    id = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    post_id = Column(String(50), unique=True, nullable=False, index=True)
    
    community_message_id = Column(Integer, ForeignKey("community_messages.id"), nullable=True)
    origin_message_id = Column(String(100), nullable=False, index=True)
    
    asset_type = Column(String(30), nullable=False)
    title = Column(String(255), nullable=False)
    copy = Column(Text, nullable=False)
    status = Column(String(30), default="APPROVED_FOR_OCI", nullable=False)
    """
CommunityLab AI - Modelos Relacionales de Base de Datos (SQLAlchemy)
Configurado con Sequence para compatibilidad 100% nativa con Oracle Cloud y SQLite.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, Sequence
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Secuencias explícitas para Oracle Database (genera id 1, 2, 3...)
user_id_seq = Sequence('user_id_seq', start=1, increment=1)
msg_id_seq = Sequence('msg_id_seq', start=1, increment=1)
asset_id_seq = Sequence('asset_id_seq', start=1, increment=1)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, user_id_seq, server_default=user_id_seq.next_value(), primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    role = Column(String(20), default="CURATOR", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    approved_assets = relationship("MarketingAsset", back_populates="approver")


class CommunityMessage(Base):
    __tablename__ = "community_messages"

    id = Column(Integer, msg_id_seq, server_default=msg_id_seq.next_value(), primary_key=True)
    message_id = Column(String(100), unique=True, nullable=False, index=True)
    source = Column(String(50), nullable=False, default="discord")
    channel = Column(String(100), nullable=False)
    author_raw = Column(String(100), nullable=False)
    author_anon = Column(String(100), nullable=False)
    raw_text = Column(Text, nullable=False)
    clean_text = Column(Text, nullable=False)

    processed = Column(Boolean, default=True, nullable=False, index=True)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sentiment = Column(String(50), nullable=True)
    topics = Column(String(255), nullable=True)
    opportunity_score = Column(Float, nullable=True)
    opportunity_type = Column(String(50), nullable=True)

    assets = relationship("MarketingAsset", back_populates="origin_message")


class MarketingAsset(Base):
    __tablename__ = "marketing_assets"

    id = Column(Integer, asset_id_seq, server_default=asset_id_seq.next_value(), primary_key=True)
    post_id = Column(String(50), unique=True, nullable=False, index=True)
    
    community_message_id = Column(Integer, ForeignKey("community_messages.id"), nullable=True)
    origin_message_id = Column(String(100), nullable=False, index=True)
    
    asset_type = Column(String(30), nullable=False)
    title = Column(String(255), nullable=False)
    copy = Column(Text, nullable=False)
    status = Column(String(30), default="APPROVED_FOR_OCI", nullable=False)
    
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    oci_object_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    origin_message = relationship("CommunityMessage", back_populates="assets")
    approver = relationship("User", back_populates="approved_assets")
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    oci_object_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    origin_message = relationship("CommunityMessage", back_populates="assets")
    approver = relationship("User", back_populates="approved_assets")