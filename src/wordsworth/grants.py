"""Reveal grants: shareable, revocable, per-PII-type authorization for
deanonymization.

A grant is the AUTHORIZATION record — "recipient R may reveal types T (for
document D, until E)". It carries no key material and no clear PII. Enforcement is
the pure `authorize()`: a revoked, expired, or document-mismatched grant
authorizes nothing, and so does an unscoped grant unless the deployment allows
global grants. Every issue/revoke is recorded in the append-only
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
    # rollen: deze grant ontleent zijn types aan een rol in plaats van aan zijn
    # eigen lijst. Óf het een óf het ander — twee bronnen voor één antwoord is
    # precies hoe autorisatiefouten ontstaan. Zie `authorize()`.
    role: str | None = None


def _is_recipient(caller: str | None, recipient: str) -> bool:
    """Exact match, deliberately.

    A recipient is a label from the same vocabulary as the caller. Two labels
    that merely resemble each other are not the same label, and a reveal is the
    wrong place to be generous: no case folding, no prefix, no wildcard. Only
    surrounding whitespace is ignored, because that is a transport artefact and
    not a different name.
    """
    if not caller or not recipient:
        return False
    return caller.strip() == recipient.strip()


def authorize(
    grant: Grant,
    document_id: uuid.UUID | None,
    requested_types: Iterable[str],
    now: datetime,
    domain: str = DEFAULT_DOMAIN,
    allow_global: bool = False,
    caller: str | None = None,
    auth_enabled: bool = False,
    resolve_role=None,
    global_roles: Iterable[str] = (),
) -> set[str]:
    """The subset of ``requested_types`` this grant permits right now — the empty
    set if the grant is revoked, expired, scoped to another document, bound to
    another domain, unscoped where global grants are not allowed, or presented by
    someone other than its recipient. Never raises for the denied case: the caller
    reveals exactly the returned types.

    ``allow_global`` defaults to False for the same reason ``domain`` defaults to
    one domain: a grant never widens implicitly. A caller that wants the
    reveal-any-document behaviour asks for it.

    ``resolve_role`` maps a role name to the types it currently allows. A grant
    that names a role gets its types from there AT THIS MOMENT — that is what
    makes switching a role off take effect at once, without any grant changing.
    Left out, a role-granted reveal authorises nothing: a caller that cannot look
    the role up does not know what it permits, and "nothing" is the only safe
    answer.

    ``global_roles`` names the roles whose grants may be unscoped even where
    ``allow_global`` is off. The exception carries a name instead of hiding
    behind a boolean, so the audit trail can show that one applied and to whom.

    ``caller`` is checked against ``grant.recipient`` only when ``auth_enabled``.
    Without caller authentication there is no caller to decide on and behaviour is
    unchanged — the documented tailnet-internal mode, the same line
    ``authorize_grant_issue`` already follows.
    """
    if grant.status != ACTIVE:
        return set()
    if auth_enabled and not _is_recipient(caller, grant.recipient):
        # A grant names WHO may reveal. Until that name is checked, the grant id
        # is a bearer token: one leak — a log line, a ticket, a screenshot — and
        # clear PII is open to whoever finds it.
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
    if grant.document_id is None:
        # Unscoped ("global") grant: reveal on every document. A capability that
        # broad is only available where the deployment allows it — of waar hij
        # op naam staat van een rol die hem mag hebben.
        #
        # Die tweede weg bestaat omdat de eerste te grof is. "Alles zien" is
        # wat een beheerder doet, en de enige manieren om dat met de vlag te
        # regelen zijn: hem omzetten (en dan mag élke ongescopete grant weer
        # alles, voor iedereen), of per document een grant uitgeven (791 stuks,
        # en morgen meer). De uitzondering hoort de naam te dragen van wie hem
        # krijgt in plaats van te schuilen achter een boolean — dan kan het
        # auditspoor achteraf laten zien dát er een uitzondering gold en voor wie.
        if not (allow_global or (grant.role and grant.role in set(global_roles))):
            return set()
    elif grant.document_id != document_id:
        return set()
    allowed = permitted_types(grant, resolve_role)
    return {t.upper() for t in requested_types if t.upper() in allowed}


def permitted_types(grant: Grant, resolve_role=None) -> set[str]:
    """De types die deze grant toestaat: uit zijn eigen lijst, of uit zijn rol.

    Noemt de grant een rol, dan wordt die **hier** opgelost — op het moment van
    beslissen, niet op het moment van uitgeven. Dat is wat een rol uitzetten
    onmiddellijk laat werken zonder dat er één grant verandert.

    Zonder `resolve_role` levert een rol-grant niets. Fail-closed: een aanroeper
    die de rol niet kan opzoeken weet niet wat hij toestaat, en dan is de enige
    veilige aanname "niets". Een terugval op `grant.allowed_types` zou hier van
    een uitgezette rol een suggestie maken.
    """
    if grant.role:
        if resolve_role is None:
            return set()
        return {t.upper() for t in resolve_role(grant.role)}
    return {t.upper() for t in grant.allowed_types}


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
        #: rollen: leeg = de grant draagt zijn eigen typelijst; gezet = hij
        #: ontleent zijn types aan die rol, opgelost bij elke beslissing.
        role: str | None = None,
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
    role: str | None = None,
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
        role=role,
    )


class InMemoryGrantStore:
    """Dict-backed ``GrantStore`` — test double and non-DB wiring option."""

    def __init__(self) -> None:
        self._d: dict[str, Grant] = {}

    def issue(self, recipient, allowed_types, actor, document_id=None, expires_at=None,
              domain=DEFAULT_DOMAIN, role=None):
        grant = _new_grant(recipient, allowed_types, actor, document_id, expires_at,
                           domain, role)
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
              domain=DEFAULT_DOMAIN, role=None):
        grant = _new_grant(recipient, allowed_types, actor, document_id, expires_at,
                           domain, role)
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
                role=grant.role,
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
            role=row.role,
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
    role: str | None = None,
) -> Grant:
    """Issue a grant and record it in the key-lifecycle audit stream (one event)."""
    grant = store.issue(recipient, allowed_types, actor, document_id, expires_at,
                        domain, role)
    key_audit.grant_issued(
        grant_id=grant.grant_id,
        recipient=grant.recipient,
        # Bij een rol-grant staat hier een lege lijst, en dat is juist: wat deze
        # grant toestaat is geen feit van dit moment maar van het moment waarop
        # iemand hem gebruikt. De rolnaam staat ernaast, zodat het spoor wel
        # zegt wáár het vandaan komt.
        allowed_types=grant.allowed_types,
        document_id=str(grant.document_id) if grant.document_id else None,
        actor=actor,
        domain=grant.domain,
        role=grant.role,
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
