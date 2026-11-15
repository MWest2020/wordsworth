# SPDX-License-Identifier: MIT
"""Groep -> rol (keycloak-groups-to-roles): rechten volgen groeplidmaatschap,
beheerd als data op één plek — de applicatie beslist niets voorbij het
opzoeken van een geverifieerde groep hier.

`roles.held_by` is de unie die de rest van het systeem gebruikt: een rol via
een grant, of via een groep, en beide respecteren `Role.active`.
"""
from __future__ import annotations

import pytest

from wordsworth import group_roles, roles
from wordsworth.key_audit_pg import PostgresKeyLifecycleAudit as _Stroom


def test_a_group_maps_to_a_role(session_factory):
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark", audit=_Stroom(s))
        s.flush()
        group_roles.set_role(s, "hr-afdeling", "hr", actor="mark", audit=_Stroom(s))
        s.flush()
        assert group_roles.roles_for(s, ["hr-afdeling"]) == {"hr"}


def test_an_unmapped_or_absent_group_grants_nothing(session_factory):
    with session_factory() as s:
        assert group_roles.roles_for(s, ["niemand"]) == frozenset()
        assert group_roles.roles_for(s, None) == frozenset()
        assert group_roles.roles_for(s, []) == frozenset()


def test_a_group_mapped_to_a_switched_off_role_grants_nothing(session_factory):
    """Dezelfde regel als een rol-grant: uitzetten werkt onmiddellijk en raakt
    de afbeelding zelf niet aan."""
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark", audit=_Stroom(s))
        group_roles.set_role(s, "hr-afdeling", "hr", actor="mark", audit=_Stroom(s))
        s.flush()
        roles.deactivate(s, "hr", actor="mark", reason="lek", audit=_Stroom(s))
        s.flush()
        assert group_roles.roles_for(s, ["hr-afdeling"]) == frozenset()
        assert group_roles.by_group(s, "hr-afdeling").role == "hr", (
            "de afbeelding zelf mag niet veranderd zijn")


def test_a_group_mapped_to_an_unknown_role_grants_nothing(session_factory):
    with session_factory() as s:
        group_roles.set_role(s, "spook", "bestaat-niet", actor="mark",
                             audit=_Stroom(s))
        s.flush()
        assert group_roles.roles_for(s, ["spook"]) == frozenset()


def test_setting_again_replaces_the_mapping(session_factory):
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark", audit=_Stroom(s))
        roles.create(s, "ict", ["EMAIL"], actor="mark", audit=_Stroom(s))
        s.flush()
        group_roles.set_role(s, "afdeling", "hr", actor="mark", audit=_Stroom(s))
        group_roles.set_role(s, "afdeling", "ict", actor="mark", audit=_Stroom(s))
        s.flush()
        assert group_roles.roles_for(s, ["afdeling"]) == {"ict"}
        assert len(group_roles.listing(s)) == 1


def test_deleting_an_unknown_mapping_is_refused(session_factory):
    with session_factory() as s:
        with pytest.raises(group_roles.GroupRoleError):
            group_roles.delete(s, "weg", actor="mark", audit=_Stroom(s))


def test_deleting_removes_the_mapping(session_factory):
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark", audit=_Stroom(s))
        group_roles.set_role(s, "afdeling", "hr", actor="mark", audit=_Stroom(s))
        s.flush()
        group_roles.delete(s, "afdeling", actor="mark", audit=_Stroom(s))
        s.flush()
        assert group_roles.roles_for(s, ["afdeling"]) == frozenset()
        assert group_roles.listing(s) == []


def test_without_a_stream_a_mapping_change_is_an_error(session_factory):
    """Dezelfde discipline als `roles._noteer`: zonder stroom is dit een fout,
    geen stille terugval."""
    from wordsworth.dossier_events import MissingAuditStream

    with session_factory() as s:
        with pytest.raises(MissingAuditStream):
            group_roles.set_role(s, "g", "hr", actor="mark", audit=None)


def test_a_mapping_change_is_audited(session_factory, tmp_path):
    from wordsworth.key_audit import JsonlKeyLifecycleAudit

    audit = JsonlKeyLifecycleAudit(tmp_path / "k.jsonl")
    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark", audit=audit)
        group_roles.set_role(s, "hr-afdeling", "hr", actor="mark", audit=audit)
        group_roles.delete(s, "hr-afdeling", actor="mark", audit=audit)
    events = [e for e in audit.events() if e.get("action") == "group_role_changed"]
    assert [e["change"] for e in events] == ["created", "deleted"]
    assert events[0]["group"] == "hr-afdeling" and events[0]["role"] == "hr"
    assert events[0]["actor"] == "mark"


# --- de unie die het systeem gebruikt (roles.held_by) -----------------------

def test_held_by_is_the_union_of_grant_and_group(session_factory):
    from wordsworth.grants import PostgresGrantStore

    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark", audit=_Stroom(s))
        s.flush()
        PostgresGrantStore(s).issue("mark", [], actor="mark", role="hr")
        group_roles.set_role(s, "hr-afdeling", "hr", actor="mark", audit=_Stroom(s))
        s.commit()

        assert roles.held_by(s, "mark", None, "hr") is True, "via de grant"
        assert roles.held_by(s, "iemand-anders", ["hr-afdeling"], "hr") is True, (
            "via de groep")
        assert roles.held_by(s, "iemand-anders", None, "hr") is False
        assert roles.held_by(s, "iemand-anders", ["andere-groep"], "hr") is False


def test_held_by_respects_active_through_either_path(session_factory):
    from wordsworth.grants import PostgresGrantStore

    with session_factory() as s:
        roles.create(s, "hr", ["PERSON"], actor="mark", audit=_Stroom(s))
        PostgresGrantStore(s).issue("mark", [], actor="mark", role="hr")
        group_roles.set_role(s, "hr-afdeling", "hr", actor="mark", audit=_Stroom(s))
        s.commit()
        roles.deactivate(s, "hr", actor="mark", reason="lek", audit=_Stroom(s))
        s.commit()

        assert roles.held_by(s, "mark", None, "hr") is False
        assert roles.held_by(s, "iemand-anders", ["hr-afdeling"], "hr") is False
