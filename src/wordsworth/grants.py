"""Reveal grants: shareable, revocable, per-PII-type authorization for
deanonymization.

A grant is the AUTHORIZATION record — "recipient R may reveal types T (for
document D, until E)". It carries no key material and no clear PII. Enforcement is
the pure `authorize()`: a revoked, expired, or document-mismatched grant
authorizes nothing. Every issue/revoke is recorded in the append-only
key-lifecycle audit stream (a global key-management fact, not a document event).

Seam note: this layer decides *whether* a reveal is permitted. Cryptographic key
hand-over (so a recipient can decrypt independently) will plug in behind this via
OpenBao in a later cycle; the grant stays the authorization of record either way."""
from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from .key_audit import KeyLifecycleAudit
from .keys import DEFAULT_DOMAIN
from .models import GrantRecord

ACTIVE = "active"
REVOKED = "revoked"


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Grant:
    grant_id: str
    recipient: str
    allowed_types: list[str]          # upper-case PII types
    document_id: uuid.UUID | None     # None = global (any document)
    status: str                       # ACTIVE | REVOKED
    created_at: datetime
    revoked_at: datetime | None
    expires_at: datetime | None
    actor: str
    # add-domain-keys: the pseudonymisation domain this grant is bound to. A
    # grant without one is bound to the default domain — never to all domains.
    domain: str = DEFAULT_DOMAIN


def authorize(
    grant: Grant,
    document_id: uuid.UUID | None,
    requested_types: Iterable[str],
    now: datetime,
    domain: str = DEFAULT_DOMAIN,
) -> set[str]:
    """The subset of ``requested_types`` this grant permits right now — the empty
    set if the grant is revoked, expired, scoped to another document, or bound to
    another domain. Never raises for the denied case: the caller reveals exactly
    the returned types."""
    if grant.status != ACTIVE:
        return set()
    if (grant.domain or DEFAULT_DOMAIN) != domain:
        return set()  # fail-safe: a grant never spans domains implicitly
    if grant.expires_at is not None:
        # Treat a tz-naive expiry as UTC so the comparison can't raise (which
        # would 500 the reveal) — fail toward denial, never toward a leak.
        expires = grant.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        cmp_now = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
        if cmp_now >= expires:
            return set()
    if grant.document_id is not None and grant.document_id != document_id:
        return set()
    allowed = {t.upper() for t in grant.allowed_types}
    return {t.upper() for t in requested_types if t.upper() in allowed}


@runtime_checkable
class GrantStore(Protocol):
    def issue(
        self,
        recipient: str,
        allowed_types: Iterable[str],
        actor: str,
        document_id: uuid.UUID | None = None,
        expires_at: datetime | None = None,
        domain: str = DEFAULT_DOMAIN,
    ) -> Grant: ...
    def get(self, grant_id: str) -> Grant | None: ...
    def revoke(self, grant_id: str, actor: str) -> None: ...


def _new_grant(
    recipient: str,
    allowed_types: Iterable[str],
    actor: str,
    document_id: uuid.UUID | None,
    expires_at: datetime | None,
    domain: str = DEFAULT_DOMAIN,
) -> Grant:
    return Grant(
        grant_id=uuid.uuid4().hex,
        recipient=recipient,
        allowed_types=[t.upper() for t in allowed_types],
        document_id=document_id,
        status=ACTIVE,
        created_at=_now(),
        revoked_at=None,
        expires_at=expires_at,
        actor=actor,
        domain=domain,
    )


class InMemoryGrantStore:
    """Dict-backed ``GrantStore`` — test double and non-DB wiring option."""

    def __init__(self) -> None:
        self._d: dict[str, Grant] = {}

    def issue(self, recipient, allowed_types, actor, document_id=None, expires_at=None,
              domain=DEFAULT_DOMAIN):
        grant = _new_grant(recipient, allowed_types, actor, document_id, expires_at, domain)
        self._d[grant.grant_id] = grant
        return grant

    def get(self, grant_id: str) -> Grant | None:
        return self._d.get(grant_id)

    def revoke(self, grant_id: str, actor: str) -> None:
        grant = self._d.get(grant_id)
        if grant is None:
            raise KeyError(grant_id)
        if grant.status == REVOKED:
            return  # idempotent
        grant.status = REVOKED
        grant.revoked_at = _now()


class PostgresGrantStore:
    """Durable ``GrantStore`` in PostgreSQL. The caller owns the transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def issue(self, recipient, allowed_types, actor, document_id=None, expires_at=None,
              domain=DEFAULT_DOMAIN):
        grant = _new_grant(recipient, allowed_types, actor, document_id, expires_at, domain)
        self._session.add(
            GrantRecord(
                grant_id=grant.grant_id,
                recipient=grant.recipient,
                allowed_types=grant.allowed_types,
                document_id=grant.document_id,
                status=grant.status,
                created_at=grant.created_at,
                revoked_at=grant.revoked_at,
                expires_at=grant.expires_at,
                actor=grant.actor,
                domain=grant.domain,
            )
        )
        self._session.flush()
        return grant

    def get(self, grant_id: str) -> Grant | None:
        row = self._session.get(GrantRecord, grant_id)
        if row is None:
            return None
        return Grant(
            grant_id=row.grant_id,
            recipient=row.recipient,
            allowed_types=list(row.allowed_types),
            document_id=row.document_id,
            status=row.status,
            created_at=row.created_at,
            revoked_at=row.revoked_at,
            expires_at=row.expires_at,
            actor=row.actor,
            domain=row.domain or DEFAULT_DOMAIN,  # legacy NULL = default domain
        )

    def revoke(self, grant_id: str, actor: str) -> None:
        row = self._session.get(GrantRecord, grant_id)
        if row is None:
            raise KeyError(grant_id)
        if row.status == REVOKED:
            return  # idempotent
        row.status = REVOKED
        row.revoked_at = _now()
        self._session.flush()


def issue_grant(
    store: GrantStore,
    key_audit: KeyLifecycleAudit,
    recipient: str,
    allowed_types: Iterable[str],
    actor: str,
    document_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
    domain: str = DEFAULT_DOMAIN,
) -> Grant:
    """Issue a grant and record it in the key-lifecycle audit stream (one event)."""
    grant = store.issue(recipient, allowed_types, actor, document_id, expires_at, domain)
    key_audit.grant_issued(
        grant_id=grant.grant_id,
        recipient=grant.recipient,
        allowed_types=grant.allowed_types,
        document_id=str(grant.document_id) if grant.document_id else None,
        actor=actor,
        domain=grant.domain,
    )
    return grant


def revoke_grant(
    store: GrantStore,
    key_audit: KeyLifecycleAudit,
    grant_id: str,
    actor: str,
) -> None:
    """Revoke a grant and record it in the key-lifecycle audit stream (one event)."""
    store.revoke(grant_id, actor)
    key_audit.grant_revoked(grant_id=grant_id, actor=actor)
