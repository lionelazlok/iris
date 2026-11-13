"""Modèle de données. Aucune image ni IrisCode en clair n'est stocké.
Les sujets sont pseudonymisés (external_ref fourni par l'application métier)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    external_ref: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | locked | revoked
    cancel_version: Mapped[int] = mapped_column(Integer, default=1)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    templates: Mapped[list["Template"]] = relationship(back_populates="subject", cascade="all, delete-orphan")


class Template(Base):
    __tablename__ = "templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"), index=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    nonce: Mapped[bytes] = mapped_column(LargeBinary(12))
    wrapped_dek: Mapped[bytes] = mapped_column(LargeBinary)
    dek_nonce: Mapped[bytes] = mapped_column(LargeBinary(12))
    kek_id: Mapped[str] = mapped_column(String(32))
    algorithm: Mapped[str] = mapped_column(String(32), default="AES-256-GCM")
    quality: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    subject: Mapped[Subject] = relationship(back_populates="templates")


class AuditLog(Base):
    """Journal append-only chaîné : hash_i = HMAC(k, hash_{i-1} || contenu_i)."""
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(32))
    subject_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome: Mapped[str] = mapped_column(String(16))
    details: Mapped[str] = mapped_column(Text, default="")
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
