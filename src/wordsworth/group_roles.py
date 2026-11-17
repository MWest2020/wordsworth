# SPDX-License-Identifier: MIT
"""Group → role mapping (keycloak-groups-to-roles).

A caller may hold a role not only by being the recipient of a grant that
names it, but also by belonging to a group — read only from the verified
identity assertion of the current request (`access_identity.py`) — that is
mapped to that role here. The mapping itself is DATA, managed behind the same
gate as `/roles`; the application decides nothing beyond looking it up
(`grants.caller_holds_role`).

This mapping never reaches a reveal: `grants.authorize` is untouched, and
holding a role through a group makes a caller the recipient of no grant.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import roles
from .models import GroupRole

GROUP_ROLE_MAPPED = "group_role_mapped"
GROUP_ROLE_UNMAPPED = "group_role_unmapped"


class GroupRoleError(ValueError):
    """A group-role mapping change that cannot happen."""


def listing(session: Session) -> list[GroupRole]:
    return list(session.execute(
        select(GroupRole).order_by(GroupRole.group, GroupRole.role)).scalars())


def by_pair(session: Session, group: str, role: str) -> GroupRole | None:
    return session.execute(
        select(GroupRole).where(GroupRole.group == group,
                                GroupRole.role == role)).scalars().first()


def map_group(session: Session, group: str, role: str, actor: str,
             audit=None) -> GroupRole:
    """Map ``group`` to ``role``. The role must exist (`GroupRoleError`, the
    same 404 idiom as `PUT /roles/{name}/types` on an unknown role). Mapping
    an already-mapped pair changes nothing and writes no event."""
    group = (group or "").strip()
    role = (role or "").strip()
    if not group:
        raise GroupRoleError("a mapping needs a group")
    if roles.by_name(session, role) is None:
        raise GroupRoleError(f"onbekende rol {role!r}")
    existing = by_pair(session, group, role)
    if existing is not None:
        return existing
    row = GroupRole(group=group, role=role, created_by=actor)
    session.add(row)
    session.flush()
    _noteer(audit, GROUP_ROLE_MAPPED, group=group, role=role, actor=actor)
    return row


def unmap_group(session: Session, group: str, role: str, actor: str,
                audit=None) -> None:
    """Remove the mapping. An absent pair changes nothing and writes no
    event — the same idempotence as mapping an existing one."""
    row = by_pair(session, group, role)
    if row is None:
        return
    session.delete(row)
    session.flush()
    _noteer(audit, GROUP_ROLE_UNMAPPED, group=group, role=role, actor=actor)


def _noteer(audit, change: str, *, group: str, role: str, actor: str) -> None:
    """Write the change to the key-lifecycle stream. No stream is a fail-loud
    error, not a silent skip — the same rule `roles._noteer` follows, for the
    same reason: a production path that can skip the audit record silently is
    how a dossier rename once went unrecorded."""
    if audit is None:
        from .dossier_events import MissingAuditStream
        raise MissingAuditStream(
            "a group-role mapping change needs the key-lifecycle stream")
    if change == GROUP_ROLE_MAPPED:
        audit.group_role_mapped(group=group, role=role, actor=actor)
    else:
        audit.group_role_unmapped(group=group, role=role, actor=actor)
