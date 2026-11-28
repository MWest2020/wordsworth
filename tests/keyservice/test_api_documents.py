"""design.md "DELETE /v1/originals/{document_id}" and "DELETE
/v1/documents/{document_id}": destroying keys, registry rows and orphaned
mappings, deleting scoped grants and keeping unscoped ones, the tombstone,
the already-tombstoned and never-seen cases, one lifecycle+audit record per
call, and no clear value, original byte or key byte anywhere."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from wordsworth.keyservice import api_documents, audit, lifecycle, serve
from wordsworth.keyservice.models import (DocumentKeyRecord, DocumentToken,
                                          KnownDocument, PiiMapping)
from wordsworth.keyservice.models_access import AccessAudit, GrantRecord, KeyLifecycleEvent
from wordsworth.transit import FakeTransit


def _app(keyservice_database_url, monkeypatch, tokens=None):
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", keyservice_database_url)
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    return serve.create_app(
        service_tokens=tokens if tokens is not None else {"tok": "ingest"},
        transit_for=lambda kek: FakeTransit())


def _client(app):
    return TestClient(app, headers={"Authorization": "Bearer tok"})


def _seal(client, document_id, domain="acme", object_key="documents/a",
         body=b"plaintext bytes"):
    return client.post(f"/v1/originals/{document_id}/seal",
                       params={"domain": domain, "object_key": object_key},
                       content=body)


def _pseudonymise(client, document_id, domain="acme", items=()):
    return client.post("/v1/pseudonymise", json={
        "document_id": str(document_id), "domain": domain, "items": list(items)})


def _grant(session, *, grant_id=None, document_id=None):
    grant = GrantRecord(
        grant_id=grant_id or str(uuid.uuid4()), recipient="someone",
        allowed_types=["PERSON"], document_id=document_id, status="active",
        created_at=datetime.now(timezone.utc), actor="ingest")
    session.add(grant)
    session.flush()
    return grant


# --- DELETE /v1/originals/{document_id} -------------------------------------

def test_destroys_all_key_rows_and_a_later_open_is_404(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        _seal(client, doc_id, object_key="documents/a")
        _seal(client, doc_id, object_key="documents/b")
        resp = client.delete(f"/v1/originals/{doc_id}")
        assert resp.status_code == 200
        assert resp.json() == {"destroyed": 2}

        opened = client.post(f"/v1/originals/{doc_id}/open",
                             params={"object_key": "documents/a", "purpose": "process"},
                             content=b"anything")
    assert opened.status_code == 404

    with keyservice_session_factory() as session:
        assert session.get(DocumentKeyRecord, "documents/a") is None
        assert session.get(DocumentKeyRecord, "documents/b") is None


def test_originals_deletion_is_idempotent(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        _seal(client, doc_id)
        first = client.delete(f"/v1/originals/{doc_id}")
        second = client.delete(f"/v1/originals/{doc_id}")
    assert first.json() == {"destroyed": 1}
    assert second.json() == {"destroyed": 0}


def test_originals_deletion_of_a_never_sealed_document_destroys_nothing(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    with _client(app) as client:
        resp = client.delete(f"/v1/originals/{uuid.uuid4()}")
    assert resp.status_code == 200
    assert resp.json() == {"destroyed": 0}


def test_originals_deletion_writes_one_lifecycle_and_one_access_record(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        _seal(client, doc_id)
        client.delete(f"/v1/originals/{doc_id}")

    with keyservice_session_factory() as session:
        access = session.query(AccessAudit).filter_by(event="delete_originals").all()
        lifecycle_events = session.query(KeyLifecycleEvent).filter_by(
            action="keys_destroyed").all()
    assert len(access) == 1
    assert access[0].payload["destroyed"] == 1
    assert len(lifecycle_events) == 1
    assert lifecycle_events[0].payload["key_ids"]


# --- DELETE /v1/documents/{document_id} --------------------------------------

def test_full_deletion_counts_tombstone_and_scoped_grant_only(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        _seal(client, doc_id, object_key="documents/a")
        _pseudonymise(client, doc_id, items=[{"type": "PERSON", "value": "Jan Jansen"}])

        with keyservice_session_factory() as session:
            scoped = _grant(session, document_id=uuid.UUID(doc_id))
            unscoped = _grant(session, document_id=None)
            session.commit()
            scoped_id, unscoped_id = scoped.grant_id, unscoped.grant_id

        resp = client.delete(f"/v1/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json() == {"keys": 1, "tokens": 1, "mappings": 1, "grants": 1}

    with keyservice_session_factory() as session:
        row = session.get(KnownDocument, uuid.UUID(doc_id))
        assert row is not None and row.deleted_at is not None
        assert session.get(GrantRecord, scoped_id) is None
        assert session.get(GrantRecord, unscoped_id) is not None
        assert session.get(DocumentKeyRecord, "documents/a") is None
        assert session.query(DocumentToken).filter_by(
            document_id=uuid.UUID(doc_id)).count() == 0


def test_shared_value_survives_deletion_of_one_document(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_a, doc_b = str(uuid.uuid4()), str(uuid.uuid4())
    with _client(app) as client:
        token_a = _pseudonymise(
            client, doc_a, items=[{"type": "PERSON", "value": "Jan Jansen"}]
        ).json()["tokens"][0]
        token_b = _pseudonymise(
            client, doc_b, items=[{"type": "PERSON", "value": "Jan Jansen"}]
        ).json()["tokens"][0]
        assert token_a == token_b

        resp = client.delete(f"/v1/documents/{doc_a}")
    assert resp.json() == {"keys": 0, "tokens": 1, "mappings": 0, "grants": 0}

    with keyservice_session_factory() as session:
        assert session.get(PiiMapping, token_a) is not None
        assert session.get(DocumentToken, (uuid.UUID(doc_a), token_a)) is None
        assert session.get(DocumentToken, (uuid.UUID(doc_b), token_b)) is not None


def test_a_later_pseudonymise_or_seal_of_a_deleted_document_is_410(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        _pseudonymise(client, doc_id)
        client.delete(f"/v1/documents/{doc_id}")
        pseudonymised = _pseudonymise(client, doc_id)
        sealed = _seal(client, doc_id)
    assert pseudonymised.status_code == 410
    assert sealed.status_code == 410


def test_an_already_tombstoned_document_deletion_counts_zero_except_new_grants(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        _pseudonymise(client, doc_id)
        first = client.delete(f"/v1/documents/{doc_id}")
        assert first.json() == {"keys": 0, "tokens": 0, "mappings": 0, "grants": 0}

        with keyservice_session_factory() as session:
            row_before = session.get(KnownDocument, uuid.UUID(doc_id))
            deleted_at_before = row_before.deleted_at
            _grant(session, document_id=uuid.UUID(doc_id))
            session.commit()

        second = client.delete(f"/v1/documents/{doc_id}")
    assert second.json() == {"keys": 0, "tokens": 0, "mappings": 0, "grants": 1}

    with keyservice_session_factory() as session:
        row_after = session.get(KnownDocument, uuid.UUID(doc_id))
        assert row_after.deleted_at == deleted_at_before


def test_a_never_seen_document_gets_no_tombstone_but_its_grants_are_deleted(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        _grant(session, document_id=doc_id)
        session.commit()

    app = _app(keyservice_database_url, monkeypatch)
    with _client(app) as client:
        resp = client.delete(f"/v1/documents/{doc_id}")
        assert resp.json() == {"keys": 0, "tokens": 0, "mappings": 0, "grants": 1}

        with keyservice_session_factory() as session:
            assert session.get(KnownDocument, doc_id) is None

        later = _pseudonymise(client, doc_id)
    assert later.status_code == 200
    with keyservice_session_factory() as session:
        row = session.get(KnownDocument, doc_id)
        assert row is not None and row.deleted_at is None


def test_document_deletion_writes_one_lifecycle_and_one_access_record(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        _pseudonymise(client, doc_id, items=[{"type": "PERSON", "value": "Jan Jansen"}])
        client.delete(f"/v1/documents/{doc_id}")

    with keyservice_session_factory() as session:
        access = session.query(AccessAudit).filter_by(event="delete_document").all()
        lifecycle_events = session.query(KeyLifecycleEvent).filter_by(
            action="document_deleted").all()
    assert len(access) == 1
    assert access[0].payload == {"keys": 0, "tokens": 1, "mappings": 1, "grants": 0}
    assert len(lifecycle_events) == 1


def test_a_failure_after_the_lifecycle_append_commits_neither(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        _seal(client, doc_id, object_key="documents/a")
        _pseudonymise(client, doc_id, items=[{"type": "PERSON", "value": "Jan Jansen"}])

    def boom(*args, **kwargs):
        raise RuntimeError("injected failure")

    with pytest.MonkeyPatch.context() as injected:
        injected.setattr(api_documents.audit, "append_access", boom)
        with pytest.raises(RuntimeError):
            with keyservice_session_factory() as session:
                api_documents.delete_document(session, uuid.UUID(doc_id), actor="ingest")
                session.commit()

    with keyservice_session_factory() as session:
        row = session.get(KnownDocument, uuid.UUID(doc_id))
        assert row is not None and row.deleted_at is None
        assert session.get(DocumentKeyRecord, "documents/a") is not None
        assert session.query(DocumentToken).filter_by(
            document_id=uuid.UUID(doc_id)).count() == 1
        assert lifecycle.verify_lifecycle_chain(session) == (True, None)
        assert audit.verify_access_chain(session) == (True, None)

    with _client(app) as client:
        resp = client.delete(f"/v1/documents/{doc_id}")
    assert resp.json() == {"keys": 1, "tokens": 1, "mappings": 1, "grants": 0}


def test_no_clear_value_or_key_byte_in_any_response_or_log_line(
        keyservice_session_factory, keyservice_database_url, monkeypatch, caplog):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    sentinel_value = "SENTINEL-VALUE-f3b1c9"
    sentinel_bytes = b"SENTINEL-ORIGINAL-BYTES-f3b1c9"
    with caplog.at_level(logging.DEBUG):
        with _client(app) as client:
            _seal(client, doc_id, body=sentinel_bytes)
            _pseudonymise(client, doc_id,
                         items=[{"type": "PERSON", "value": sentinel_value}])
            originals_resp = client.delete(f"/v1/originals/{doc_id}")
            document_resp = client.delete(f"/v1/documents/{doc_id}")

    assert sentinel_value not in originals_resp.text
    assert sentinel_value not in document_resp.text
    assert sentinel_bytes.decode() not in originals_resp.text
    assert sentinel_bytes.decode() not in document_resp.text
    assert sentinel_value not in caplog.text
    assert sentinel_bytes.decode() not in caplog.text

    with keyservice_session_factory() as session:
        access_dump = str([(r.event, r.payload) for r in session.query(AccessAudit).all()])
        lifecycle_dump = str([(e.action, e.payload)
                              for e in session.query(KeyLifecycleEvent).all()])
    assert sentinel_value not in access_dump
    assert sentinel_value not in lifecycle_dump
    assert sentinel_bytes.decode() not in access_dump
    assert sentinel_bytes.decode() not in lifecycle_dump
