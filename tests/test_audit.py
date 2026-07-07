import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

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
