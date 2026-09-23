# SPDX-License-Identifier: MIT
"""The key-lifecycle stream in PostgreSQL (key-audit-in-postgres).

Until 2026-09-23 this stream was a JSONL file on an emptyDir: append-only and
gone at every restart. These tests pin the three properties that replace that,
against the real schema that `init_schema` creates -- the trigger included,
because a test that only proves the code never updates a row proves nothing
about what the database allows.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from wordsworth import key_audit_pg
from wordsworth.key_audit import JsonlKeyLifecycleAudit
from wordsworth.key_audit_pg import PostgresKeyLifecycleAudit


def test_an_event_lands_in_the_table(session):
    PostgresKeyLifecycleAudit(session).grant_revoked(grant_id="g1", actor="mark")
    session.commit()

    events = PostgresKeyLifecycleAudit(session).events()
    assert [(e["action"], e["grant_id"], e["actor"]) for e in events] == [
        ("grant_revoked", "g1", "mark")]


def test_it_commits_with_the_change_or_not_at_all(session):
    """The event lives in the caller's transaction. If the change is rolled
    back, the record of it goes too -- and the other way round, a committed
    change cannot lose its record to a second, separate commit."""
    PostgresKeyLifecycleAudit(session).grant_revoked(grant_id="g1", actor="mark")
    session.rollback()
    assert PostgresKeyLifecycleAudit(session).events() == []


def test_an_update_is_refused_by_the_database(session):
    PostgresKeyLifecycleAudit(session).grant_revoked(grant_id="g1", actor="mark")
    session.commit()
    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(text("UPDATE key_lifecycle_events SET actor = 'someone'"))
    session.rollback()


def test_a_delete_is_refused_by_the_database(session):
    PostgresKeyLifecycleAudit(session).grant_revoked(grant_id="g1", actor="mark")
    session.commit()
    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(text("DELETE FROM key_lifecycle_events"))
    session.rollback()


def test_the_chain_holds_across_every_kind_of_event(session):
    a = PostgresKeyLifecycleAudit(session)
    a.grant_issued(grant_id="g1", recipient="mark@westerweel.work",
                   allowed_types=["PERSON"], document_id=None, actor="mark")
    a.role_changed(role="lezer", change="created", allowed_types=["PERSON"],
                   active=True, actor="mark")
    a.dossier_renamed(dossier_id="d1", old="oud", new="nieuw", documents=3,
                      actor="mark")
    a.rotation(old_key_id="k1", new_key_id="k2", entries_reencrypted=7,
               actor="mark")
    a.grant_revoked(grant_id="g1", actor="mark")
    session.commit()
    assert key_audit_pg.verify_chain(session) == (True, None)


def test_a_uuid_in_the_payload_does_not_break_verification(session):
    """What is hashed must be what JSONB hands back. A UUID object hashed as-is
    and read back as a string would make an honest chain fail."""
    import uuid
    PostgresKeyLifecycleAudit(session).grant_issued(
        grant_id="g1", recipient="mark@westerweel.work", allowed_types=["PERSON"],
        document_id=uuid.uuid4(), actor="mark")
    session.commit()
    assert key_audit_pg.verify_chain(session) == (True, None)


def test_tampering_is_detected_at_the_altered_event(session):
    a = PostgresKeyLifecycleAudit(session)
    a.grant_issued(grant_id="g1", recipient="mark@westerweel.work",
                   allowed_types=["PERSON"], document_id=None, actor="mark")
    a.grant_revoked(grant_id="g1", actor="mark")
    session.commit()
    first = session.execute(text("SELECT min(seq) FROM key_lifecycle_events")).scalar()
    # An elevated-rights tamper that bypasses the append-only trigger.
    session.execute(text("ALTER TABLE key_lifecycle_events "
                         "DISABLE TRIGGER key_lifecycle_no_mutation"))
    session.execute(text("UPDATE key_lifecycle_events SET actor = 'someone-else' "
                         "WHERE seq = :s"), {"s": first})
    session.execute(text("ALTER TABLE key_lifecycle_events "
                         "ENABLE TRIGGER key_lifecycle_no_mutation"))
    session.commit()
    assert key_audit_pg.verify_chain(session) == (False, first)


def test_events_have_the_shape_the_jsonl_driver_had(session, tmp_path):
    """Readers were written against the JSONL shape. Same keys, same values --
    the storage changed, what a reader sees did not."""
    jsonl = JsonlKeyLifecycleAudit(tmp_path / "s.jsonl")
    pg = PostgresKeyLifecycleAudit(session)
    for a in (jsonl, pg):
        a.dossier_renamed(dossier_id="d1", old="oud", new="nieuw", documents=3,
                          actor="mark")
    session.commit()
    strip = lambda e: {k: v for k, v in e.items() if k != "ts"}  # noqa: E731
    assert strip(pg.events()[0]) == strip(jsonl.events()[0])


def test_the_export_is_the_rows_in_order_with_their_chain(session):
    a = PostgresKeyLifecycleAudit(session)
    a.grant_issued(grant_id="g1", recipient="mark@westerweel.work",
                   allowed_types=["PERSON"], document_id=None, actor="mark")
    a.grant_revoked(grant_id="g1", actor="mark")
    session.commit()
    import json
    rows = [json.loads(line) for line in key_audit_pg.export_jsonl(session).splitlines()]
    assert [r["action"] for r in rows] == ["grant_issued", "grant_revoked"]
    assert rows[1]["prev_hash"] == rows[0]["hash"]


def test_a_rename_through_the_cli_is_recorded(session_factory, monkeypatch):
    """The gap this change exists for, tested at the entry point Mark ran.

    Until 2026-09-23 `wordsworth-dossier-hernoem` passed no stream, the rename
    returned silently, and no rename was ever recorded. Testing `rename()` with
    a stream passed in would have been green all along; the bug lived in the
    caller. So this drives `main_rename` itself.
    """
    from wordsworth import dossier_tools, dossiers
    from wordsworth.pipeline import register

    with session_factory() as s:
        d = dossiers.ensure(s, "corpus-2026-09")
        doc = register(s, "documents/cli-rename")
        s.flush()
        dossiers.add(s, d.id, doc.id, actor="test")
        s.commit()

    monkeypatch.setattr(dossier_tools, "_sessie", session_factory)
    assert dossier_tools.main_rename(
        ["corpus-2026-09", "Gooise Meren Woo 2022", "--actor", "mark"]) == 0

    with session_factory() as s:
        events = PostgresKeyLifecycleAudit(s).events()
        assert [e["action"] for e in events] == ["dossier_renamed"]
        e = events[0]
        assert (e["old"], e["new"], e["documents"], e["actor"]) == (
            "corpus-2026-09", "Gooise Meren Woo 2022", 1, "mark")
