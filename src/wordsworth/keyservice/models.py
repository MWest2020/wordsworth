"""The key service's own schema: ``KeyServiceBase``, a separate
``DeclarativeBase`` from wordsworth's ``Base`` (``wordsworth.models``). No
table here has a foreign key to a wordsworth table, and this module imports
nothing from ``wordsworth.models`` -- the same ``Table`` object registered on
two metadatas would make ``KeyServiceBase.metadata.create_all`` create
wordsworth's tables too (design.md "Reuse and imports", rule 1).

Tables marked "copied" below match a wordsworth model's column names, types
and nullability (compared by ``tests/keyservice/test_drift.py``), as their
own class -- never imported from wordsworth. ``known_documents`` and
``document_tokens`` are new: the service's own record of which documents and
tokens it has seen (design.md "Schema")."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class KeyServiceBase(DeclarativeBase):
    pass


class KnownDocument(KeyServiceBase):
    """A document the service has registered (design.md "Schema"): recorded
    here before either ``document_keys`` or ``document_tokens`` is written
    for it. ``deleted_at`` tombstones the row on deletion -- it is never
    removed, because both of those tables hold a real foreign key to
    ``id`` here."""

    __tablename__ = "known_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc))
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class DocumentToken(KeyServiceBase):
    """The token registry (ADR-0009 amendment, finding 2 of the architect
    FAIL): which tokens belong to which document, filled only by the
    service's own pseudonymise step (``key-service-vault``). ``source``
    distinguishes a token minted here from one copied over at cutover, the
    same role as wordsworth's ``DocumentPseudonym.source``."""

    __tablename__ = "document_tokens"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("known_documents.id"), primary_key=True)
    token: Mapped[str] = mapped_column(String, primary_key=True)
    #: minted | copied_minted | copied_backfilled
    source: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc))


class KeyVaultRecord(KeyServiceBase):
    """Copied from ``wordsworth.models.KeyVaultRecord``."""

    __tablename__ = "key_vault"

    key_id: Mapped[str] = mapped_column(String, primary_key=True)
    scope: Mapped[str] = mapped_column(String, nullable=False, index=True)
    wrapped_material: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("uq_keyservice_key_vault_active_scope", "scope", unique=True,
              postgresql_where=text("status = 'active'")),
    )


class PiiMapping(KeyServiceBase):
    """Copied from ``wordsworth.models.PiiMapping``."""

    __tablename__ = "pii_mappings"

    pseudonym: Mapped[str] = mapped_column(String, primary_key=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_id: Mapped[str] = mapped_column(String, nullable=False)
    norm_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentKeyRecord(KeyServiceBase):
    """Copied from ``wordsworth.document_keys.DocumentKeyRecord``, except
    ``document_id`` refers to this service's own ``known_documents.id``,
    never to a wordsworth ``documents.id`` (design.md "Schema")."""

    __tablename__ = "document_keys"

    object_key: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("known_documents.id"), nullable=False, index=True)
    key_id: Mapped[str] = mapped_column(String, nullable=False)
    kek_ref: Mapped[str] = mapped_column(String, nullable=False)
    wrapped_material: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sealed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
