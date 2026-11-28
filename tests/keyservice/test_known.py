"""design.md "known_documents": first-sight domain recording, the 409/410
refusals, and the registry advisory lock (4781)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from wordsworth.keyservice import known
from wordsworth.keyservice.models import KnownDocument


def test_first_sight_records_the_domain(keyservice_session_factory):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        known.lock_registry(session)
        known.ensure_known(session, doc_id, "example")
        session.commit()

    with keyservice_session_factory() as session:
        row = session.get(KnownDocument, doc_id)
        assert row is not None
        assert row.domain == "example"
        assert row.deleted_at is None


def test_same_domain_again_does_not_raise(keyservice_session_factory):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        known.lock_registry(session)
        known.ensure_known(session, doc_id, "example")
        session.commit()

    with keyservice_session_factory() as session:
        known.lock_registry(session)
        known.ensure_known(session, doc_id, "example")  # does not raise
        session.commit()


def test_a_different_domain_later_raises_domain_conflict(keyservice_session_factory):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        known.lock_registry(session)
        known.ensure_known(session, doc_id, "example")
        session.commit()

    with keyservice_session_factory() as session:
        known.lock_registry(session)
        with pytest.raises(known.DomainConflict):
            known.ensure_known(session, doc_id, "other")


def test_a_tombstoned_document_raises_document_deleted(keyservice_session_factory):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        session.add(KnownDocument(
            id=doc_id, domain="example",
            registered_at=datetime.now(timezone.utc),
            deleted_at=datetime.now(timezone.utc)))
        session.commit()

    with keyservice_session_factory() as session:
        known.lock_registry(session)
        with pytest.raises(known.DocumentDeleted):
            known.ensure_known(session, doc_id, "example")


def test_lock_registry_takes_the_advisory_lock(keyservice_session_factory):
    with keyservice_session_factory() as session:
        known.lock_registry(session)
        held = session.execute(
            text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
                 "AND objid = :k"), {"k": known.REGISTRY_LOCK_KEY}
        ).scalar_one()
        assert held >= 1
