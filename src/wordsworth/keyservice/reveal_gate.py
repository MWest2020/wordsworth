"""The one decision both reveal routes make, in the order design.md "Order
inside the service" fixes (ADR-0009, amended 2026-11-26): judge the grant on
its own domain, then on the document's; apply the VC gate; check the
tombstone; only then compute what is authorized -- all before any token,
mapping or key is touched. Mirrors wordsworth's own ``reveal_gate.decide``,
over this service's own rows (grants, known_documents) and its own role
table, never wordsworth's.

Every caller this does not cover gets ``REFUSAL``, raised fresh each time
(an ``HTTPException`` carries no state worth sharing) -- no 404, no 409, no
410 except to a caller the grant already covers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from wordsworth.grants import Grant, authorize, permitted_types
from wordsworth.keys import DEFAULT_DOMAIN
from wordsworth.vc import VcError, apply_vc_gate

from . import known, roles
from .grants import KeyServiceGrantStore

#: The constant wordsworth's own ``reveal_gate.REFUSAL`` uses today, reused
#: unchanged on both routes -- one refusal body for every cause a caller is
#: not covered for.
REFUSAL = {"status_code": 403, "detail": "grant not applicable"}

#: The one role whose grants may be unscoped even where
#: ``allow_global_grants`` is off (design.md "Identity").
GLOBAL_ROLES = frozenset({roles.ADMIN})


@dataclass
class Decision:
    """What a route needs to answer, once the grant covers this document."""

    grant: Grant
    domain: str
    authorized: set[str]
    withheld: set[str]
    vc_audit: dict


def decide(
    session: Session,
    grant_id: str,
    document_id: UUID,
    requested_types: Iterable[str] | None,
    *,
    caller: str | None,
    allow_global: bool,
    now: datetime,
    vc_public_key,
    vc_expected_vct: str | None,
    vc_expected_issuer: str | None,
    vc_required: bool,
    x_vc: str | None,
) -> Decision:
    """Refuse, or return what the route needs. Two ``authorize()`` calls on
    the grant's own types before the document is read (its own domain, then
    the document's), a third once the real request's types are known
    (design.md "Order inside the service", step 8) -- dropping any of the
    three either brings back the existence oracle or loses a binding."""

    def resolve_role(name: str) -> set[str]:
        return set(roles.resolve(session, name).types)

    grant = KeyServiceGrantStore(session).get(grant_id)
    if grant is None:
        raise HTTPException(**REFUSAL)

    permitted = permitted_types(grant, resolve_role)
    if not authorize(grant, document_id, permitted, now,
                     grant.domain or DEFAULT_DOMAIN, allow_global, caller,
                     True, resolve_role=resolve_role, global_roles=GLOBAL_ROLES):
        raise HTTPException(**REFUSAL)

    # Only now: the document. Both reads always run, so an unknown grant id
    # costs exactly what an unknown document costs -- neither answers faster.
    row = known.lookup(session, document_id)
    if row is None:
        raise HTTPException(**REFUSAL)
    covered = authorize(grant, document_id, permitted, now, row.domain,
                        allow_global, caller, True, resolve_role=resolve_role,
                        global_roles=GLOBAL_ROLES)
    if not covered:
        raise HTTPException(**REFUSAL)

    # The VC gate is pure (no reads) and part of "covered": a caller it
    # rejects hears nothing about deletion either.
    try:
        vc_types, vc_audit = apply_vc_gate(
            covered, x_vc, public_key=vc_public_key, expected_vct=vc_expected_vct,
            expected_issuer=vc_expected_issuer, required=vc_required, now=now)
    except VcError as exc:
        raise HTTPException(status_code=403, detail=f"vc rejected: {exc}")

    if row.deleted_at is not None:
        raise HTTPException(status_code=410, detail="document deleted")

    requested = {t.upper() for t in requested_types} if requested_types else permitted
    authorized = authorize(grant, document_id, requested, now, row.domain,
                           allow_global, caller, True, resolve_role=resolve_role,
                           global_roles=GLOBAL_ROLES)
    authorized &= vc_types
    withheld = requested - authorized

    return Decision(grant=grant, domain=row.domain, authorized=authorized,
                    withheld=withheld, vc_audit=vc_audit)
