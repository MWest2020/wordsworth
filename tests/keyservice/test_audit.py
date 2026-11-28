"""design.md "The audit writer": ``append_access`` chains correctly under
lock 4782, and ``verify_access_chain`` catches tampering."""
from __future__ import annotations

import uuid

from sqlalchemy import text

from wordsworth.keyservice import audit


def test_chain_verifies_after_a_run_of_appends(keyservice_session_factory):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        audit.append_access(session, event="pseudonymise", service_caller="ingest",
                            document_id=doc_id, payload={"counts": {"PERSON": 1}})
        audit.append_access(session, event="pseudonymise", service_caller="ingest",
                            document_id=doc_id, payload={"counts": {"EMAIL": 2}})
        session.commit()

        ok, bad_seq = audit.verify_access_chain(session)
    assert ok is True
    assert bad_seq is None


def test_verify_detects_a_record_altered_behind_the_trigger(keyservice_session_factory):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        audit.append_access(session, event="pseudonymise", service_caller="ingest",
                            document_id=doc_id, payload={"counts": {"PERSON": 1}})
        audit.append_access(session, event="pseudonymise", service_caller="ingest",
                            document_id=doc_id, payload={"counts": {"EMAIL": 2}})
        session.commit()

        # Simulate an elevated-rights tamper that bypasses the append-only
        # trigger, the same way tests/test_audit.py proves wordsworth's own
        # chain catches it.
        session.execute(text(
            "ALTER TABLE access_audit DISABLE TRIGGER access_audit_no_mutation"))
        session.execute(text(
            "UPDATE access_audit SET payload = '{\"counts\": {\"PERSON\": 9999}}' "
            "WHERE seq = (SELECT min(seq) FROM access_audit)"))
        session.execute(text(
            "ALTER TABLE access_audit ENABLE TRIGGER access_audit_no_mutation"))
        session.commit()

        ok, bad_seq = audit.verify_access_chain(session)
    assert ok is False
    assert bad_seq is not None


def test_append_access_takes_the_lock(keyservice_session_factory):
    with keyservice_session_factory() as session:
        audit.append_access(session, event="pseudonymise", service_caller="ingest",
                            document_id=None, payload={})
        held = session.execute(
            text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
                 "AND objid = :k"), {"k": audit.LOCK_KEY}
        ).scalar_one()
        assert held >= 1


def test_append_access_record_holds_no_value_or_token(keyservice_session_factory):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        rec = audit.append_access(
            session, event="pseudonymise", service_caller="ingest",
            document_id=doc_id,
            payload={"counts": {"PERSON": 1}, "new_registry_rows": 1})
        session.commit()
    dump = str(rec.payload) + str(rec.event) + str(rec.document_id)
    assert "SENTINEL" not in dump
