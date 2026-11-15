# SPDX-License-Identifier: MIT
"""Group -> role mapping (keycloak-groups-to-roles).

An organisation manages people in groups at its identity provider; rights
should follow that membership, managed as data in one place, with the
application deciding nothing beyond looking a verified group up here — the
same posture `roles.py` already takes toward "who someone is".

A group grants a role only while the mapping says so AND the role itself is
switched on: the same rule a role-named grant already obeys
(`roles.resolve`/`grants.caller_holds_role`), resolved NOW rather than frozen
at mapping time. Removing a group from someone in Keycloak, or removing the
mapping here, takes effect at that caller's next assertion — nothing about a
group is cached beyond the request.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import GroupRole, Role


class GroupRoleError(ValueError):
    """A group-role mapping action that cannot be done."""


def set_role(session: Session, group: str, role: str, actor: str,
             audit=None) -> GroupRole:
    """Map ``group`` to ``role``, replacing any role it was mapped to before."""
    group = (group or "").strip()
    role = (role or "").strip()
    if not group:
        raise GroupRoleError("een afbeelding heeft een groep nodig")
    if not role:
        raise GroupRoleError("een afbeelding heeft een rol nodig")
    row = by_group(session, group)
    if row is None:
        row = GroupRole(group=group, role=role, created_by=actor,
                        created_at=datetime.now(timezone.utc))
        session.add(row)
        change = "created"
    else:
        row.role = role
        change = "updated"
    session.flush()
    _noteer(audit, row, change, actor)
    return row


def by_group(session: Session, group: str) -> GroupRole | None:
    return session.execute(
        select(GroupRole).where(GroupRole.group == group)).scalars().first()


def listing(session: Session) -> list[GroupRole]:
    return list(session.execute(
        select(GroupRole).order_by(GroupRole.group)).scalars())


def delete(session: Session, group: str, actor: str, audit=None) -> None:
    row = by_group(session, group)
    if row is None:
        raise GroupRoleError(f"onbekende groep-afbeelding {group!r}")
    session.delete(row)
    session.flush()
    _noteer(audit, row, "deleted", actor)


def roles_for(session: Session, groups) -> frozenset[str]:
    """Which roles the given (verified) groups currently hold — mapped AND
    active. A group mapped to an unknown or switched-off role grants nothing,
    the same fail-closed answer `roles.resolve` gives a role-named grant."""
    names = {g.strip() for g in (groups or ()) if g and g.strip()}
    if not names:
        return frozenset()
    mapped = {row.role for row in session.execute(
        select(GroupRole).where(GroupRole.group.in_(names))).scalars()}
    if not mapped:
        return frozenset()
    return frozenset(session.execute(
        select(Role.name).where(Role.name.in_(mapped), Role.active.is_(True))
    ).scalars())


def _noteer(audit, row: GroupRole, change: str, actor: str) -> None:
    """Zelfde discipline als `roles._noteer`: zonder stroom is dit een fout,
    geen stille terugval."""
    if audit is None:
        from .dossier_events import MissingAuditStream
        raise MissingAuditStream(
            "a group-role change needs the key-lifecycle stream")
    audit.group_role_changed(group=row.group, role=row.role, change=change,
                             actor=actor)
