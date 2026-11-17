# SPDX-License-Identifier: MIT
"""Group -> role mapping (keycloak-groups-to-roles): the data, and how
`caller_holds_role` reads it. `Role.active` is checked first for both a grant
and a group -- a switched-off role is held by nobody, whichever source named
it."""
from __future__ import annotations

from datetime import datetime, timezone

from wordsworth import group_roles, roles
from wordsworth.grants import PostgresGrantStore, caller_holds_role
from wordsworth.key_audit_pg import PostgresKeyLifecycleAudit as _Stroom
from wordsworth.models import GrantRecord


def test_a_group_mapped_to_an_active_role_is_held(session_factory):
    with session_factory() as s:
        roles.create(s, "hr", ["EMAIL"], actor="mark", audit=_Stroom(s))
        s.flush()
        group_roles.map_role(s, "hr-afdeling", "hr", actor="mark", audit=_Stroom(s))
        s.commit()
        assert caller_holds_role(s, None, "hr", groups=("hr-afdeling",)) is True
        assert caller_holds_role(s, None, "hr", groups=("iets-anders",)) is False


def test_mapping_onto_an_unknown_role_is_refused(session_factory):
    with session_factory() as s:
        try:
            group_roles.map_role(s, "hr-afdeling", "weg", actor="mark", audit=_Stroom(s))
            assert False, "had moeten weigeren"
        except group_roles.GroupRoleError:
            pass
        assert group_roles.listing(s) == []


def test_mapping_an_existing_pair_again_is_idempotent_and_writes_no_event(
        session_factory, tmp_path):
    from wordsworth.key_audit import JsonlKeyLifecycleAudit

    audit = JsonlKeyLifecycleAudit(tmp_path / "lifecycle.jsonl")
    with session_factory() as s:
        roles.create(s, "hr", ["EMAIL"], actor="mark", audit=audit)
        s.flush()
        group_roles.map_role(s, "hr-afdeling", "hr", actor="mark", audit=audit)
        group_roles.map_role(s, "hr-afdeling", "hr", actor="mark", audit=audit)
        s.commit()
    events = [e for e in audit.events() if e.get("action") == "group_role_mapped"]
    assert len(events) == 1


def test_unmapping_an_absent_pair_is_idempotent_and_writes_no_event(
        session_factory, tmp_path):
    from wordsworth.key_audit import JsonlKeyLifecycleAudit

    audit = JsonlKeyLifecycleAudit(tmp_path / "lifecycle.jsonl")
    with session_factory() as s:
        removed = group_roles.unmap_role(s, "hr-afdeling", "hr", actor="mark",
                                         audit=audit)
        s.commit()
    assert removed is False
    assert [e for e in audit.events() if e.get("action") == "group_role_unmapped"] == []


def test_switching_off_the_role_closes_the_group_too(session_factory):
    with session_factory() as s:
        roles.create(s, "hr", ["EMAIL"], actor="mark", audit=_Stroom(s))
        s.flush()
        group_roles.map_role(s, "hr-afdeling", "hr", actor="mark", audit=_Stroom(s))
        s.commit()
        assert caller_holds_role(s, None, "hr", groups=("hr-afdeling",)) is True
        roles.deactivate(s, "hr", actor="mark", reason="lek", audit=_Stroom(s))
        s.flush()
        assert caller_holds_role(s, None, "hr", groups=("hr-afdeling",)) is False
        roles.activate(s, "hr", actor="mark", reason="gedicht", audit=_Stroom(s))
        s.flush()
        assert caller_holds_role(s, None, "hr", groups=("hr-afdeling",)) is True


def test_an_unknown_role_name_is_held_by_nobody_even_with_a_grant(session_factory):
    """`caller_holds_role` now checks `Role.active` first, for both sources —
    this is the fix: a grant naming a role nobody created is not held."""
    with session_factory() as s:
        s.add(GrantRecord(grant_id="g1", recipient="mark", allowed_types=[],
                          document_id=None, status="active",
                          created_at=datetime.now(timezone.utc),
                          revoked_at=None, expires_at=None, actor="t", domain=None,
                          role="spookrol"))
        s.commit()
        assert caller_holds_role(s, "mark", "spookrol") is False


def test_a_switched_off_role_grant_no_longer_holds_the_role_and_comes_back(
        session_factory):
    """The bug this change fixes: before, `caller_holds_role` never checked
    `Role.active`, so a grant naming a switched-off role still held it."""
    with session_factory() as s:
        roles.create(s, roles.ADMIN, ["PERSON"], actor="installatie",
                     audit=_Stroom(s))
        s.flush()
        gs = PostgresGrantStore(s)
        gs.issue("mark", [], actor="t", role=roles.ADMIN)
        s.commit()
        assert caller_holds_role(s, "mark", roles.ADMIN) is True
        roles.deactivate(s, roles.ADMIN, actor="mark", reason="breakglass",
                         audit=_Stroom(s))
        s.flush()
        assert caller_holds_role(s, "mark", roles.ADMIN) is False
        roles.activate(s, roles.ADMIN, actor="mark", reason="weer aan",
                       audit=_Stroom(s))
        s.flush()
        assert caller_holds_role(s, "mark", roles.ADMIN) is True
