"""design.md "The key-lifecycle chain": ``append_lifecycle`` chains
correctly under lock 4783, ``verify_lifecycle_chain`` catches tampering, and
a record hashed by wordsworth's own ``key_audit_pg`` construction from the
same fields gets the same hash -- so a verifier that reads one reads the
other."""
from __future__ import annotations

import uuid

from sqlalchemy import text

from wordsworth import key_audit_pg
from wordsworth.hashing import GENESIS_HASH, compute_hash
from wordsworth.keyservice import lifecycle


def test_chain_verifies_after_a_run_of_appends(keyservice_session_factory):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        lifecycle.append_lifecycle(
            session, action="keys_destroyed", actor="ingest",
            payload={"document_id": str(doc_id), "key_ids": ["abc"]})
        lifecycle.append_lifecycle(
            session, action="document_deleted", actor="ingest",
            payload={"document_id": str(doc_id), "destroyed_key_ids": [],
                    "deleted_grant_ids": []})
        session.commit()

        ok, bad_seq = lifecycle.verify_lifecycle_chain(session)
    assert ok is True
    assert bad_seq is None


def test_verify_detects_a_record_altered_behind_the_trigger(keyservice_session_factory):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        lifecycle.append_lifecycle(
            session, action="keys_destroyed", actor="ingest",
            payload={"document_id": str(doc_id), "key_ids": ["abc"]})
        lifecycle.append_lifecycle(
            session, action="keys_destroyed", actor="ingest",
            payload={"document_id": str(doc_id), "key_ids": ["def"]})
        session.commit()

        session.execute(text(
            "ALTER TABLE key_lifecycle_events DISABLE TRIGGER "
            "key_lifecycle_no_mutation"))
        session.execute(text(
            "UPDATE key_lifecycle_events SET payload = '{\"key_ids\": [\"tampered\"]}' "
            "WHERE seq = (SELECT min(seq) FROM key_lifecycle_events)"))
        session.execute(text(
            "ALTER TABLE key_lifecycle_events ENABLE TRIGGER "
            "key_lifecycle_no_mutation"))
        session.commit()

        ok, bad_seq = lifecycle.verify_lifecycle_chain(session)
    assert ok is False
    assert bad_seq is not None


def test_append_lifecycle_takes_the_lock(keyservice_session_factory):
    with keyservice_session_factory() as session:
        lifecycle.append_lifecycle(session, action="keys_destroyed",
                                   actor="ingest", payload={})
        held = session.execute(
            text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
                 "AND objid = :k"), {"k": lifecycle.LOCK_KEY}
        ).scalar_one()
        assert held >= 1


def test_hash_matches_wordsworths_own_key_audit_pg_construction(
        keyservice_session_factory):
    """Same canonical content (``ts``, ``action``, ``actor``, ``payload``),
    same ``hashing.compute_hash`` -- the two chains are not merely similar,
    they are verifiable by each other's construction."""
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        event = lifecycle.append_lifecycle(
            session, action="document_deleted", actor="ingest",
            payload={"document_id": str(doc_id), "destroyed_key_ids": ["abc"],
                    "deleted_grant_ids": []})
        session.commit()

    want = compute_hash(
        GENESIS_HASH,
        key_audit_pg._content(
            ts=key_audit_pg._iso(event.ts), action=event.action,
            actor=event.actor, payload=event.payload))
    assert event.hash == want
