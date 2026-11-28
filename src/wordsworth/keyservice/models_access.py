"""The service's authorisation and audit tables: grants, roles and the two
hash-chained streams. Split from ``models.py`` only because that file hit the
200-line limit (design.md "Layout": "split further if the rule needs it") --
same ``KeyServiceBase``, same rules (no wordsworth foreign key, nothing
imported from ``wordsworth.models``)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .models import KeyServiceBase


class GrantRecord(KeyServiceBase):
    """Copied from ``wordsworth.models.GrantRecord``. ``document_id`` is
    nullable and never a foreign key (design.md "Schema"): a grant may name a
    document the service has not seen, and it then covers nothing."""

    __tablename__ = "grants"

    grant_id: Mapped[str] = mapped_column(String, primary_key=True)
    recipient: Mapped[str] = mapped_column(String, nullable=False)
    allowed_types: Mapped[list] = mapped_column(JSONB, nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)


class Role(KeyServiceBase):
    """Copied from ``wordsworth.models.Role``."""

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    allowed_types: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[str] = mapped_column(String, nullable=False)


class GroupRole(KeyServiceBase):
    """Copied from ``wordsworth.models.GroupRole``."""

    __tablename__ = "group_roles"

    group: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String, primary_key=True)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc))


class KeyLifecycleEvent(KeyServiceBase):
    """Copied from ``wordsworth.models.KeyLifecycleEvent``: the service's own
    hash-chained authorisation trail, append-only by the same trigger
    function as wordsworth's (``db.py``)."""

    __tablename__ = "key_lifecycle_events"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prev_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class AccessAudit(KeyServiceBase):
    """New (design.md "Schema"): the service's own open/reveal audit stream.
    ``event`` replaces wordsworth's ``from_state``/``to_state`` -- this
    stream has no document state machine, only events. Append-only,
    hash-chained under its own advisory lock, never wordsworth's 4771 or
    its own key-lifecycle lock 4783 (``key-service-vault`` is the first
    change to write here)."""

    __tablename__ = "access_audit"

    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event: Mapped[str] = mapped_column(String, nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True)
    service_caller: Mapped[str] = mapped_column(String, nullable=False)
    caller: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prev_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
