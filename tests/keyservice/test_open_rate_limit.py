"""design.md "The rate limit": a token bucket per calling service on
``POST /v1/originals/{document_id}/open``, checked after the purpose and
query are validated (so the order is 401, 422, 429), unaffected by another
caller, and shared across replicas through ``service_state``."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from wordsworth.keyservice import serve
from wordsworth.keyservice.models_access import AccessAudit
from wordsworth.transit import FakeTransit


def _app(keyservice_database_url, monkeypatch, *, burst="2", rate="60",
         tokens=None):
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", keyservice_database_url)
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    monkeypatch.setenv("KEYSERVICE_OPEN_BURST", burst)
    monkeypatch.setenv("KEYSERVICE_OPEN_RATE_PER_MINUTE", rate)
    return serve.create_app(
        service_tokens=tokens if tokens is not None else
        {"tok-a": "ingest", "tok-b": "search"},
        transit_for=lambda kek: FakeTransit())


def _open(client, token, object_key="documents/ghost", purpose="process"):
    return client.post(
        f"/v1/originals/{uuid.uuid4()}/open",
        params={"object_key": object_key, "purpose": purpose}, content=b"",
        headers={"Authorization": f"Bearer {token}"})


def test_a_burst_past_the_limit_is_429_with_retry_after(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch, burst="2")
    with TestClient(app) as client:
        first = _open(client, "tok-a")
        second = _open(client, "tok-a")
        third = _open(client, "tok-a")
    # Under the burst: no key for a made-up object, so 404 -- the request
    # reached the rest of the route's table, which is the point.
    assert first.status_code == 404
    assert second.status_code == 404
    assert third.status_code == 429
    assert "Retry-After" in third.headers
    assert int(third.headers["Retry-After"]) >= 1


def test_another_caller_is_not_affected_by_the_first_callers_burst(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch, burst="1")
    with TestClient(app) as client:
        _open(client, "tok-a")
        refused = _open(client, "tok-a")
        other = _open(client, "tok-b")
    assert refused.status_code == 429
    assert other.status_code == 404


def test_missing_purpose_over_the_limit_is_422_not_429(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch, burst="1")
    with TestClient(app) as client:
        _open(client, "tok-a")  # spends the only token
        resp = client.post(
            f"/v1/originals/{uuid.uuid4()}/open",
            params={"object_key": "documents/ghost"}, content=b"",
            headers={"Authorization": "Bearer tok-a"})
    assert resp.status_code == 422


def test_two_app_instances_refusing_the_same_caller_write_one_record(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    # Two independent `create_app()` calls -- two engines, two session
    # factories -- against the same database: what "replica" means here.
    app_a = _app(keyservice_database_url, monkeypatch, burst="0")
    app_b = _app(keyservice_database_url, monkeypatch, burst="0")
    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        first = _open(client_a, "tok-a")
        second = _open(client_b, "tok-a")
    assert first.status_code == 429
    assert second.status_code == 429

    with keyservice_session_factory() as session:
        refused = [r for r in session.query(AccessAudit).all()
                   if r.event == "open_refused"]
    assert len(refused) == 1
