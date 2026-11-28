"""design.md "GET /v1/metrics": the service-token gate, its two counters,
no value/document id/object key in the output, and that the route is never
rate-limited."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from wordsworth.keyservice import serve
from wordsworth.transit import FakeTransit


def _app(keyservice_database_url, monkeypatch, *, burst="2", rate="60"):
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", keyservice_database_url)
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    monkeypatch.setenv("KEYSERVICE_OPEN_BURST", burst)
    monkeypatch.setenv("KEYSERVICE_OPEN_RATE_PER_MINUTE", rate)
    return serve.create_app(
        service_tokens={"tok": "ingest"}, transit_for=lambda kek: FakeTransit())


def test_metrics_without_a_token_is_401(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch)
    with TestClient(app) as client:
        resp = client.get("/v1/metrics")
    assert resp.status_code == 401
    assert "keyservice" not in resp.text


def test_metrics_counts_opens_and_refusals_with_no_value_or_key(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch, burst="1")
    headers = {"Authorization": "Bearer tok"}
    with TestClient(app) as client:
        doc_id = str(uuid.uuid4())
        sealed = client.post(
            f"/v1/originals/{doc_id}/seal",
            params={"domain": "acme", "object_key": "documents/a"},
            content=b"plaintext", headers=headers)
        client.post(
            f"/v1/originals/{doc_id}/open",
            params={"object_key": "documents/a", "purpose": "process"},
            content=sealed.content, headers=headers)
        # Spends past the burst of one -> one refusal.
        client.post(
            f"/v1/originals/{doc_id}/open",
            params={"object_key": "documents/a", "purpose": "process"},
            content=sealed.content, headers=headers)
        resp = client.get("/v1/metrics", headers=headers)
    assert resp.status_code == 200
    body = resp.text
    assert 'keyservice_opens_total{caller="ingest",purpose="process"} 1' in body
    assert 'keyservice_open_refusals_total{caller="ingest",reason="rate"} 1' in body
    assert "documents/a" not in body
    assert "plaintext" not in body
    assert doc_id not in body


def test_metrics_is_never_refused_even_called_past_the_open_limit(
        keyservice_session_factory, keyservice_database_url, monkeypatch):
    app = _app(keyservice_database_url, monkeypatch, burst="1")
    headers = {"Authorization": "Bearer tok"}
    with TestClient(app) as client:
        statuses = [client.get("/v1/metrics", headers=headers).status_code
                    for _ in range(10)]
    assert all(status == 200 for status in statuses)


def test_app_mounts_no_path_keyed_limiter_middleware():
    app = serve.create_app(
        service_tokens={"tok": "ingest"}, transit_for=lambda kek: FakeTransit())
    names = {m.cls.__name__ for m in app.user_middleware}
    assert "RateLimitMiddleware" not in names
