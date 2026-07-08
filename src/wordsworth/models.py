"""SQLAlchemy models. ``documents`` holds no current_state column — the current
state is DERIVED from the latest audit record (audit table = single source of
truth). ``audit_records`` is append-only (enforced by a trigger, see db.py)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    object_key: Mapped[str] = mapped_column(String, nullable=False)


class AuditRecord(Base):
    __tablename__ = "audit_records"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    from_state: Mapped[str | None] = mapped_column(String, nullable=True)
    to_state: Mapped[str] = mapped_column(String, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    step: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # prev_hash UNIQUE enforces a single linear chain: two records cannot claim
    # the same predecessor, so a fork fails at insert time.
    prev_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class DocumentText(Base):
    """Derived working data: the ANONYMIZED text only. Never clear PII, so it is
    mutable (not the append-only audit table) and holds nothing sensitive."""

    __tablename__ = "document_texts"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), primary_key=True
    )
    anonymized_text: Mapped[str] = mapped_column(String, nullable=False)


class PiiMapping(Base):
    """Separated encrypted mapping store: pseudonym -> AES-GCM ciphertext of the
    original PII. Holds only ciphertext, never clear PII, and never lives in the
    document. One row per pseudonym."""

    __tablename__ = "pii_mappings"

    pseudonym: Mapped[str] = mapped_column(String, primary_key=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
