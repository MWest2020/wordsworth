"""Reveal grants — DB integration (runs in CI against real Postgres)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from wordsworth.grants import PostgresGrantStore, authorize
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
