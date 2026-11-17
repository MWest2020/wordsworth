# SPDX-License-Identifier: MIT
"""Group -> role mapping (keycloak-groups-to-roles).

A row says "members of `group` hold `role`" -- data, managed here, not a
second place a role is decided. `grants.caller_holds_role` is the only reader;
it checks `Role.active` first for both a grant and a group, so a mapping onto
a switched-off role opens nothing, same as a grant naming it.

``PUT`` for a role that does not exist is refused with 404, like
``PUT /roles/{name}/types``: a mapping onto nothing is not silently accepted.
``PUT`` of an existing pair and ``DELETE`` of an absent one are idempotent and
write no event -- only a REAL change is a fact worth a record.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import GroupRole, Role


class GroupRoleError(ValueError):
    """A group-role mapping that cannot be made."""


@dataclass(frozen=True)
class MapResult:
    row: GroupRole
    changed: bool


def listing(session: Session) -> list[GroupRole]:
    return list(session.execute(
        select(GroupRole).order_by(GroupRole.group, GroupRole.role)).scalars())


def _row(session: Session, group: str, role: str) -> GroupRole | None:
    return session.get(GroupRole, {"group": group, "role": role})


def map_role(session: Session, group: str, role: str, actor: str,
            audit=None) -> MapResult:
    """Map ``group`` to ``role``. 404-worthy (`GroupRoleError`) when ``role``
    does not exist; idempotent (no event) when the pair already exists."""
    group = (group or "").strip()
    role = (role or "").strip()
    if not group:
        raise GroupRoleError("een group heeft een naam nodig")
    if session.execute(
            select(Role).where(Role.name == role)).scalars().first() is None:
        raise GroupRoleError(f"onbekende rol {role!r}")
    existing = _row(session, group, role)
    if existing is not None:
        return MapResult(existing, changed=False)
    row = GroupRole(group=group, role=role, created_by=actor)
    session.add(row)
    session.flush()
    _noteer_mapped(audit, group, role, actor)
    return MapResult(row, changed=True)


def unmap_role(session: Session, group: str, role: str, actor: str,
              audit=None) -> bool:
    """Remove the mapping, if there is one. Idempotent: removing an absent
    pair changes nothing and writes no event. Returns whether a row was
    removed."""
    row = _row(session, group, role)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    _noteer_unmapped(audit, group, role, actor)
    return True


def _noteer_mapped(audit, group: str, role: str, actor: str) -> None:
    if audit is None:
        from .dossier_events import MissingAuditStream
        raise MissingAuditStream("a group-role mapping needs the key-lifecycle stream")
    audit.group_role_mapped(group=group, role=role, actor=actor)


def _noteer_unmapped(audit, group: str, role: str, actor: str) -> None:
    if audit is None:
        from .dossier_events import MissingAuditStream
        raise MissingAuditStream("a group-role mapping needs the key-lifecycle stream")
    audit.group_role_unmapped(group=group, role=role, actor=actor)
