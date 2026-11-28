"""The build's gate in place of a real-OpenBao smoke run (tasks.md, design.md
"Second amendment"): the builder's sandbox has no `bao`/`vault` binary and no
reachable OpenBao. This is the automated seal->open round trip against a
Transit-compatible fake (`FakeTransit`), covering both open failure modes, run
in CI. The real-OpenBao smoke itself is `key-service-cutover`'s post-deploy
task, not this one."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from wordsworth.keyservice import serve
from wordsworth.transit import FakeTransit


def _app(keyservice_database_url, monkeypatch):
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", keyservice_database_url)
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    return serve.create_app(
        service_tokens={"tok": "ingest"},
        transit_for=lambda kek: FakeTransit())


def test_seal_open_round_trip_and_both_failure_modes_against_fake_transit(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    from wordsworth.keyservice.models import DocumentKeyRecord

    app = _app(keyservice_database_url, monkeypatch)
    doc_id = str(uuid.uuid4())
    original = b"a sealed original's plaintext bytes"

    with TestClient(app, headers={"Authorization": "Bearer tok"}) as client:
        sealed = client.post(
            f"/v1/originals/{doc_id}/seal",
            params={"domain": "acme", "object_key": "documents/smoke"},
            content=original)
        assert sealed.status_code == 200

        opened = client.post(
            f"/v1/originals/{doc_id}/open",
            params={"object_key": "documents/smoke", "purpose": "seal_verify"},
            content=sealed.content)
        assert opened.status_code == 200
        assert opened.content == original

    # Failure mode 1: a tampered wrapped key -> 409, reason "unwrap". A fresh
    # app -- a cold unwrap cache -- forces a real unwrap instead of serving
    # the key already cached in this process from the seal above.
    with keyservice_session_factory() as session:
        row = session.get(DocumentKeyRecord, "documents/smoke")
        row.wrapped_material = (
            bytes([row.wrapped_material[0] ^ 0x01]) + row.wrapped_material[1:])
        session.commit()

    cold_app = _app(keyservice_database_url, monkeypatch)
    with TestClient(cold_app, headers={"Authorization": "Bearer tok"}) as client:
        unwrap_failure = client.post(
            f"/v1/originals/{doc_id}/open",
            params={"object_key": "documents/smoke", "purpose": "seal_verify"},
            content=sealed.content)
        assert unwrap_failure.status_code == 409

    # Failure mode 2: a tampered envelope -> 409, reason "envelope". A fresh
    # object key (so its key row is untampered) sealed, then its sealed bytes
    # flipped -- isolates the envelope failure from the key one above.
    with TestClient(app, headers={"Authorization": "Bearer tok"}) as client:
        sealed2 = client.post(
            f"/v1/originals/{doc_id}/seal",
            params={"domain": "acme", "object_key": "documents/smoke-2"},
            content=original)
        tampered = sealed2.content[:-1] + bytes([sealed2.content[-1] ^ 0x01])
        envelope_failure = client.post(
            f"/v1/originals/{doc_id}/open",
            params={"object_key": "documents/smoke-2", "purpose": "seal_verify"},
            content=tampered)
        assert envelope_failure.status_code == 409

    from wordsworth.keyservice.models_access import AccessAudit
    with keyservice_session_factory() as session:
        reasons = {r.payload.get("reason") for r in session.query(AccessAudit)
                  .filter_by(event="open_failed").all()}
    assert reasons == {"unwrap", "envelope"}
