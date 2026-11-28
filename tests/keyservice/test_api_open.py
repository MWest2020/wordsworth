"""design.md "POST /v1/originals/{document_id}/open": the round trip, the
purpose list, the 404/503/409 cases and their audit records, and no original
or key byte in any log line."""
from __future__ import annotations

import logging
import uuid

import httpx
from fastapi.testclient import TestClient

from wordsworth.keyservice import serve
from wordsworth.transit import FakeTransit


class _RefusingTransit:
    """Raises Transit failures ``doc_keys._classify`` recognises as
    ``KeyBackendUnavailable`` -- a connect error, not an arbitrary exception
    (design.md: "anything else propagates as a 500")."""

    def wrap(self, plaintext: bytes) -> bytes:
        raise httpx.ConnectError("key service down")

    def unwrap(self, ciphertext: bytes) -> bytes:
        raise httpx.ConnectError("key service down")


def _app(keyservice_database_url, monkeypatch, tokens=None, transit_for=None):
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", keyservice_database_url)
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    return serve.create_app(
        service_tokens=tokens if tokens is not None else {"tok": "ingest"},
        transit_for=transit_for if transit_for is not None else (lambda kek: FakeTransit()))


def _client(app):
    return TestClient(app, headers={"Authorization": "Bearer tok"})


def _seal(client, document_id, object_key="documents/a", body=b"plaintext bytes"):
    return client.post(
        f"/v1/originals/{document_id}/seal",
        params={"domain": "acme", "object_key": object_key}, content=body)


def _open(client, document_id, object_key="documents/a", purpose="process", body=b""):
    return client.post(
        f"/v1/originals/{document_id}/open",
        params={"object_key": object_key, "purpose": purpose}, content=body)


def test_seal_open_round_trip_returns_the_original_bytes(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        sealed = _seal(client, doc_id)
        resp = _open(client, doc_id, body=sealed.content)
    assert resp.status_code == 200
    assert resp.content == b"plaintext bytes"


def test_purpose_missing_is_422_and_decrypts_nothing(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        sealed = _seal(client, doc_id)
        resp = client.post(
            f"/v1/originals/{doc_id}/open",
            params={"object_key": "documents/a"}, content=sealed.content)
    assert resp.status_code == 422


def test_purpose_outside_the_list_is_422(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        sealed = _seal(client, doc_id)
        resp = _open(client, doc_id, purpose="something_else", body=sealed.content)
    assert resp.status_code == 422


def test_body_over_the_bound_is_413(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    monkeypatch.setenv("KEYSERVICE_MAX_ORIGINAL_BYTES", "4")
    app = _app(keyservice_database_url, monkeypatch)
    with _client(app) as client:
        resp = _open(client, str(uuid.uuid4()), body=b"too many bytes")
    assert resp.status_code == 413


def test_no_row_for_object_key_under_this_document_is_404_and_audited(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    with _client(app) as client:
        resp = _open(client, str(uuid.uuid4()), object_key="documents/ghost",
                     body=b"anything")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "no key for this object"

    from wordsworth.keyservice.models_access import AccessAudit
    with keyservice_session_factory() as session:
        records = session.query(AccessAudit).all()
    assert len(records) == 1
    assert records[0].event == "open_refused"
    assert records[0].payload["reason"] == "no_key"


def test_row_belonging_to_another_document_is_404(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_a, doc_b = str(uuid.uuid4()), str(uuid.uuid4())
    with _client(app) as client:
        sealed = _seal(client, doc_a)
        resp = _open(client, doc_b, body=sealed.content)
    assert resp.status_code == 404


def test_tampered_wrapped_key_is_409_unwrap_and_audited(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    from wordsworth.keyservice.models import DocumentKeyRecord

    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        sealed = _seal(client, doc_id)

    with keyservice_session_factory() as session:
        row = session.get(DocumentKeyRecord, "documents/a")
        row.wrapped_material = (
            bytes([row.wrapped_material[0] ^ 0x01]) + row.wrapped_material[1:])
        session.commit()

    # A fresh app -- a cold unwrap cache -- forces a real unwrap instead of
    # serving the key seal already cached in this process.
    cold_app = _app(keyservice_database_url, monkeypatch)
    with _client(cold_app) as client:
        resp = _open(client, doc_id, body=sealed.content)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "sealed object does not open"
    assert resp.content != b"plaintext bytes"  # never the original, on any path

    from wordsworth.keyservice.models_access import AccessAudit
    with keyservice_session_factory() as session:
        records = [r for r in session.query(AccessAudit).all() if r.event == "open_failed"]
    assert len(records) == 1
    assert records[0].payload["reason"] == "unwrap"


def test_tampered_envelope_is_409_envelope_and_audited(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        sealed = _seal(client, doc_id)
        tampered = sealed.content[:-1] + bytes([sealed.content[-1] ^ 0x01])
        resp = _open(client, doc_id, body=tampered)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "sealed object does not open"
    assert resp.content != b"plaintext bytes"  # never the original, on any path

    from wordsworth.keyservice.models_access import AccessAudit
    with keyservice_session_factory() as session:
        records = [r for r in session.query(AccessAudit).all() if r.event == "open_failed"]
    assert len(records) == 1
    assert records[0].payload["reason"] == "envelope"


def test_transit_unreachable_is_503_with_no_audit_record(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        sealed = _seal(client, doc_id)

    down_app = _app(keyservice_database_url, monkeypatch,
                    transit_for=lambda kek: _RefusingTransit())
    with _client(down_app) as client:
        resp = _open(client, doc_id, body=sealed.content)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "key service unavailable"

    from wordsworth.keyservice.models_access import AccessAudit
    with keyservice_session_factory() as session:
        records = [r for r in session.query(AccessAudit).all() if r.document_id == uuid.UUID(doc_id)]
    assert all(r.event != "open_failed" and r.event != "open" for r in records)


def test_successful_open_writes_one_access_audit_record_with_its_purpose(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    with _client(app) as client:
        sealed = _seal(client, doc_id)
        _open(client, doc_id, purpose="reanonymize", body=sealed.content)

    from wordsworth.keyservice.models_access import AccessAudit
    with keyservice_session_factory() as session:
        records = [r for r in session.query(AccessAudit).all() if r.event == "open"]
    assert len(records) == 1
    assert records[0].payload["purpose"] == "reanonymize"
    assert "plaintext bytes" not in str(records[0].payload)


def test_no_original_or_key_byte_in_any_log_line(
        keyservice_session_factory, keyservice_database_url, monkeypatch, caplog):
    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    sentinel = b"SENTINEL-ORIGINAL-BYTES-f3b1c9"
    with caplog.at_level(logging.DEBUG):
        with _client(app) as client:
            sealed = _seal(client, doc_id, body=sentinel)
            resp = _open(client, doc_id, body=sealed.content)
    assert resp.status_code == 200
    assert resp.content == sentinel
    assert sentinel.decode() not in caplog.text
