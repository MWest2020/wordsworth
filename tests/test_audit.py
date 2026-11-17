import json
import threading

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from race_setup import run, wait_for_a_lock_waiter
from wordsworth import audit
from wordsworth.hashing import GENESIS_HASH
from wordsworth.models import Document


def _doc(session) -> "uuid.UUID":  # noqa: F821
    doc = Document(object_key="k")
    session.add(doc)
    session.flush()
    return doc.id


def test_append_links_predecessor(session):
    did = _doc(session)
    r1 = audit.append(session, document_id=did, from_state=None,
                      to_state="registered", step="register")
    r2 = audit.append(session, document_id=did, from_state="registered",
                      to_state="extractable", step="profile",
                      payload={"chars": 50, "pages": 1, "bytes": 10})
    session.commit()
    assert r1.prev_hash == GENESIS_HASH
    assert r2.prev_hash == r1.hash
    ok, bad = audit.verify_chain(session)
    assert ok is True and bad is None


def test_export_mirrors_table(session):
    did = _doc(session)
    rec = audit.append(session, document_id=did, from_state=None,
                       to_state="registered", step="register")
    session.commit()
    lines = audit.export_jsonl(session).splitlines()
    assert len(lines) == 1
    exported = json.loads(lines[0])
    assert exported["to_state"] == "registered"
    assert exported["prev_hash"] == GENESIS_HASH
    assert exported["hash"] == rec.hash


def test_append_only_enforced_by_trigger(session):
    did = _doc(session)
    audit.append(session, document_id=did, from_state=None,
                 to_state="registered", step="register")
    session.commit()
    with pytest.raises(DatabaseError):
        session.execute(text("UPDATE audit_records SET to_state = 'x'"))
    session.rollback()
    with pytest.raises(DatabaseError):
        session.execute(text("DELETE FROM audit_records"))
    session.rollback()


def test_verify_detects_tamper(session):
    did = _doc(session)
    audit.append(session, document_id=did, from_state=None,
                 to_state="registered", step="register")
    audit.append(session, document_id=did, from_state="registered",
                 to_state="extractable", step="profile",
                 payload={"chars": 50, "pages": 1, "bytes": 9})
    session.commit()
    # Simulate an elevated-rights tamper that bypasses the append-only trigger.
    session.execute(text("ALTER TABLE audit_records DISABLE TRIGGER audit_no_mutation"))
    session.execute(text(
        "UPDATE audit_records SET payload = '{\"chars\": 9999}' "
        "WHERE seq = (SELECT min(seq) FROM audit_records)"
    ))
    session.execute(text("ALTER TABLE audit_records ENABLE TRIGGER audit_no_mutation"))
    session.commit()
    ok, bad = audit.verify_chain(session)
    assert ok is False and bad is not None


def test_lock_chain_then_append_in_one_session_returns(session):
    """Re-entrant per session (deleted-document-answers-410, task 1.2): a
    route that locks and then appends does not block itself."""
    did = _doc(session)
    audit.lock_chain(session)
    audit.append(session, document_id=did, from_state=None,
                to_state="registered", step="register")
    session.commit()  # would hang on a non-re-entrant lock


def test_a_second_sessions_lock_chain_waits_for_the_first(session_factory):
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()

    def holder():
        with session_factory() as s:
            audit.lock_chain(s)
            paused.set()
            assert resume.wait(30), "never resumed"
            s.commit()

    def waiter():
        with session_factory() as s:
            audit.lock_chain(s)
            result["locked"] = True
            s.commit()

    first = run(errors, "holder", holder)
    assert paused.wait(10)
    second = run(errors, "waiter", waiter)
    try:
        wait_for_a_lock_waiter(session_factory)
    finally:
        resume.set()
        first.join(30)
        second.join(30)

    assert not errors, errors
    assert result["locked"] is True
