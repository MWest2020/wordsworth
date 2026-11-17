"""Reveal grants — DB integration (runs in CI against real Postgres)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from wordsworth import roles
from wordsworth.grants import PostgresGrantStore, authorize, caller_holds_role
from wordsworth.key_audit_pg import PostgresKeyLifecycleAudit
from wordsworth.models import GrantRecord, GroupRole
from wordsworth.pipeline import register


def test_postgres_grant_roundtrip_issue_get_revoke(session):
    doc = register(session, "g")
    session.commit()
    store = PostgresGrantStore(session)

    grant = store.issue("R", ["PERSON", "email"], actor="mark", document_id=doc.id)
    session.commit()

    got = store.get(grant.grant_id)
    assert got is not None
    assert got.allowed_types == ["PERSON", "EMAIL"]     # upper-cased, persisted
    assert got.document_id == doc.id
    assert got.status == "active"

    now = datetime.now(timezone.utc)
    assert authorize(got, doc.id, {"PERSON", "BSN"}, now) == {"PERSON"}
    assert authorize(got, uuid.uuid4(), {"PERSON"}, now) == set()  # other document

    store.revoke(grant.grant_id, actor="mark")
    session.commit()
    revoked = store.get(grant.grant_id)
    assert revoked.status == "revoked" and revoked.revoked_at is not None
    assert authorize(revoked, doc.id, {"PERSON"}, now) == set()


# --- keycloak-groups-to-roles: caller_holds_role ----------------------------

def _grant_record(recipient, role):
    return GrantRecord(
        grant_id=uuid.uuid4().hex, recipient=recipient, allowed_types=[],
        document_id=None, status="active", created_at=datetime.now(timezone.utc),
        revoked_at=None, expires_at=None, actor="t", domain=None, role=role)


def test_an_unknown_role_opens_nothing(session):
    """No `Role` row at all -- the fix does not only catch an inactive one."""
    session.add(_grant_record("mark", "beheerder"))
    session.commit()
    assert caller_holds_role(session, "mark", "beheerder") is False


def test_a_switched_off_role_opens_nothing_then_restores(session):
    """Proof for task 1: a grant naming a switched-off role opens the gate
    again the moment the role is switched back on, without the grant
    changing."""
    ka = PostgresKeyLifecycleAudit(session)
    roles.create(session, "beheerder", ["PERSON"], actor="mark", audit=ka)
    session.add(_grant_record("mark", "beheerder"))
    session.commit()
    assert caller_holds_role(session, "mark", "beheerder") is True

    roles.deactivate(session, "beheerder", actor="mark", reason="lek", audit=ka)
    session.commit()
    assert caller_holds_role(session, "mark", "beheerder") is False

    roles.activate(session, "beheerder", actor="mark", reason="terug", audit=ka)
    session.commit()
    assert caller_holds_role(session, "mark", "beheerder") is True


def test_a_mapped_group_opens_an_active_role(session):
    ka = PostgresKeyLifecycleAudit(session)
    roles.create(session, "beheerder", ["PERSON"], actor="mark", audit=ka)
    session.add(GroupRole(group="ict", role="beheerder", created_by="mark"))
    session.commit()

    assert caller_holds_role(session, "mark", "beheerder", groups=("ict",)) is True
    assert caller_holds_role(session, "mark", "beheerder", groups=()) is False
    assert caller_holds_role(session, "mark", "beheerder",
                             groups=("iets-anders",)) is False


def test_a_mapped_group_opens_nothing_while_the_role_is_off(session):
    ka = PostgresKeyLifecycleAudit(session)
    roles.create(session, "beheerder", ["PERSON"], actor="mark", audit=ka)
    session.add(GroupRole(group="ict", role="beheerder", created_by="mark"))
    session.commit()
    roles.deactivate(session, "beheerder", actor="mark", reason="lek", audit=ka)
    session.commit()

    assert caller_holds_role(session, "mark", "beheerder", groups=("ict",)) is False


def test_no_caller_opens_nothing_even_with_a_mapped_group(session):
    ka = PostgresKeyLifecycleAudit(session)
    roles.create(session, "beheerder", ["PERSON"], actor="mark", audit=ka)
    session.add(GroupRole(group="ict", role="beheerder", created_by="mark"))
    session.commit()

    assert caller_holds_role(session, None, "beheerder", groups=("ict",)) is False
