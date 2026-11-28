"""The service's own roles: resolution only (design.md "Identity") -- no
create/deactivate/activate here; the management endpoints come with
``key-service-cutover``. Mirrors ``wordsworth.roles``' semantics (an
inactive or unknown role permits nothing, never a fallback) over the
service's own ``Role`` table (``models_access.py``) -- never wordsworth's."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import lifecycle
from .models_access import Role

#: Mirrors ``wordsworth.roles.ADMIN``'s value: the one role
#: ``wordsworth-keyservice-init`` ensures exists (design.md "Identity"), and
#: the one role name ``reveal_gate.decide`` lets bypass the global-grants
#: setting (``global_roles``).
ADMIN = "beheerder"


@dataclass(frozen=True)
class Resolved:
    """What a role permits right now, plus why -- an empty set can mean
    "no such role" or "switched off", and a caller deciding a reveal does
    not need to tell those apart, but a test does."""

    types: frozenset[str]
    reason: str


def resolve(session: Session, name: str | None) -> Resolved:
    """What this role currently permits -- never a fallback to a grant's own
    type list or a previous version of the role. Switching a role off takes
    effect at once, without any grant changing."""
    if not name:
        return Resolved(frozenset(), "no role")
    role = session.execute(select(Role).where(Role.name == name)).scalars().first()
    if role is None:
        return Resolved(frozenset(), "unknown role")
    if not role.active:
        return Resolved(frozenset(), "role inactive")
    return Resolved(frozenset(role.allowed_types or ()), "role active")


def ensure_admin_role(session: Session, actor: str) -> str:
    """The admin role, created at install time if missing (design.md
    "Identity"; mirrors ``wordsworth.bootstrap.ensure_admin_role``). An
    existing role -- active or not -- is left untouched: a redeploy must
    never silently restore a role an operator narrowed or switched off."""
    from wordsworth.pii_categories import known_types

    existing = session.execute(select(Role).where(Role.name == ADMIN)).scalars().first()
    if existing is not None:
        return (f"role {ADMIN!r} already exists "
                f"({len(existing.allowed_types)} types, "
                f"{'active' if existing.active else 'INACTIVE'}) -- left untouched")
    types = sorted(known_types())
    session.add(Role(name=ADMIN, allowed_types=types, active=True, created_by=actor))
    session.flush()
    lifecycle.append_lifecycle(
        session, action="role_created", actor=actor,
        payload={"role": ADMIN, "allowed_types": types})
    return f"role {ADMIN!r} created with all {len(types)} types"
