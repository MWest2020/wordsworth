"""design.md "POST /v1/originals/{document_id}/seal": the three seal rules,
the refusals, known_documents sharing seal's domain check with pseudonymise,
the audit record, and no original or key byte in a log line or audit
record."""
from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from wordsworth.keyservice import serve
from wordsworth.keyservice.models import DocumentKeyRecord, KnownDocument
from wordsworth.transit import FakeTransit


class _RefusingTransit:
    def wrap(self, plaintext: bytes) -> bytes:
        raise RuntimeError("key service down")

    def unwrap(self, ciphertext: bytes) -> bytes:
        raise RuntimeError("key service down")


def _app(keyservice_database_url, monkeypatch, tokens=None, transit_for=None):
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", keyservice_database_url)
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    return serve.create_app(
        service_tokens=tokens if tokens is not None else {"tok": "ingest"},
        transit_for=transit_for if transit_for is not None else (lambda kek: FakeTransit()))


def _client(app):
    return TestClient(app, headers={"Authorization": "Bearer tok"})


def _seal(client, document_id, domain="acme", object_key="documents/a", body=b"plaintext bytes"):
    return client.post(
        f"/v1/originals/{document_id}/seal",
        params={"domain": domain, "object_key": object_key},
        content=body)


def test_first_seal_mints_and_returns_sealed_bytes_with_key_id(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        resp = _seal(client, doc_id)
    assert resp.status_code == 200
    assert "X-Key-Id" in resp.headers
    assert resp.content != b"plaintext bytes"

    with keyservice_session_factory() as session:
        row = session.get(DocumentKeyRecord, "documents/a")
    assert row is not None
    assert row.sealed_at is not None
    assert row.key_id == resp.headers["X-Key-Id"]


def test_second_seal_reuses_the_key_and_old_copy_still_opens(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        first = _seal(client, doc_id)
        second = _seal(client, doc_id, body=b"plaintext bytes, take two")
    assert first.headers["X-Key-Id"] == second.headers["X-Key-Id"]

    from wordsworth import originals_envelope
    from wordsworth.keyservice.doc_keys import DocumentKeys
    with keyservice_session_factory() as session:
        key = DocumentKeys(lambda kek: FakeTransit()).unwrap(session, "documents/a")
    opened_first = originals_envelope.open(
        key.material, key.key_id, "documents/a", first.content)
    assert opened_first == b"plaintext bytes"


def test_seal_of_object_key_owned_by_another_document_is_409_and_writes_nothing(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_a, doc_b = str(uuid.uuid4()), str(uuid.uuid4())
    with _client(app) as client:
        _seal(client, doc_a)
        resp = _seal(client, doc_b)
    assert resp.status_code == 409

    with keyservice_session_factory() as session:
        row = session.get(DocumentKeyRecord, "documents/a")
    assert str(row.document_id) == doc_a


def test_body_over_the_bound_is_413(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    monkeypatch.setenv("KEYSERVICE_MAX_ORIGINAL_BYTES", "4")
    app = _app(keyservice_database_url, monkeypatch)
    with _client(app) as client:
        resp = _seal(client, str(uuid.uuid4()), body=b"too many bytes")
    assert resp.status_code == 413


@pytest.mark.parametrize("domain", ["", "has/slash"])
def test_invalid_domain_is_422(
        keyservice_session_factory, keyservice_database_url, monkeypatch, domain):
    app = _app(keyservice_database_url, monkeypatch)
    with _client(app) as client:
        resp = _seal(client, str(uuid.uuid4()), domain=domain)
    assert resp.status_code == 422


def test_document_known_in_another_domain_is_409(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        _seal(client, doc_id, domain="acme")
        resp = _seal(client, doc_id, domain="other", object_key="documents/b")
    assert resp.status_code == 409

    with keyservice_session_factory() as session:
        assert session.get(DocumentKeyRecord, "documents/b") is None


def test_tombstoned_document_is_410(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    from datetime import datetime, timezone

    doc_id = uuid.uuid4()
    with keyservice_session_factory() as session:
        session.add(KnownDocument(id=doc_id, domain="acme",
                                  registered_at=datetime.now(timezone.utc),
                                  deleted_at=datetime.now(timezone.utc)))
        session.commit()

    app = _app(keyservice_database_url, monkeypatch)
    with _client(app) as client:
        resp = _seal(client, str(doc_id))
    assert resp.status_code == 410


def test_transit_down_is_503_and_commits_nothing(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch,
              transit_for=lambda kek: _RefusingTransit())
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        resp = _seal(client, doc_id)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "key service unavailable"

    with keyservice_session_factory() as session:
        assert session.get(KnownDocument, uuid.UUID(doc_id)) is None
        assert session.get(DocumentKeyRecord, "documents/a") is None
        from wordsworth.keyservice.models_access import AccessAudit
        assert session.query(AccessAudit).count() == 0


def test_a_document_sealed_after_pseudonymised_in_another_domain_is_409(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        client.post("/v1/pseudonymise", json={
            "document_id": doc_id, "domain": "acme", "items": []})
        resp = _seal(client, doc_id, domain="other")
    assert resp.status_code == 409


def test_a_document_pseudonymised_after_sealed_in_another_domain_is_409(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        _seal(client, doc_id, domain="acme")
        resp = client.post("/v1/pseudonymise", json={
            "document_id": doc_id, "domain": "other", "items": []})
    assert resp.status_code == 409


def test_one_access_audit_record_per_seal_with_minted_flag(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        _seal(client, doc_id)

    from wordsworth.keyservice.models_access import AccessAudit
    with keyservice_session_factory() as session:
        records = session.query(AccessAudit).all()
    assert len(records) == 1
    assert records[0].event == "seal"
    assert "plaintext bytes" not in str(records[0].payload)
    assert records[0].payload["minted"] is True


def test_no_original_or_key_byte_in_any_log_line(
        keyservice_session_factory, keyservice_database_url, monkeypatch, caplog):
    app = _app(keyservice_database_url, monkeypatch)
    sentinel = b"SENTINEL-ORIGINAL-BYTES-f3b1c9"
    with caplog.at_level(logging.DEBUG):
        with _client(app) as client:
            resp = _seal(client, str(uuid.uuid4()), body=sentinel)
    assert resp.status_code == 200
    assert sentinel.decode() not in caplog.text
    assert resp.headers["X-Key-Id"] not in caplog.text
