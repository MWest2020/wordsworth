"""Full-stack checks of the composition root: `/health` and the `/v1`
prefix, wired exactly as design.md "Service authentication" and "Refuse to
start" describe."""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.keyservice import serve
from wordsworth.keyservice.db import make_engine
from wordsworth.transit import FakeTransit


def _running_app(keyservice_database_url, monkeypatch, tokens=None):
    monkeypatch.setenv("KEYSERVICE_DATABASE_URL", keyservice_database_url)
    monkeypatch.delenv("WORDSWORTH_DATABASE_URL", raising=False)
    # A transit_for stub, never called by these tests: design.md "Settings
    # and the Transit seam" -- passing one means the OpenBao settings are
    # not required, which is what these /health and auth tests care about.
    return serve.create_app(service_tokens=tokens if tokens is not None else {},
                            transit_for=lambda kek: FakeTransit())


def test_health_ok_with_reachable_database(keyservice_database_url, monkeypatch):
    app = _running_app(keyservice_database_url, monkeypatch)
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_503_when_database_unreachable(monkeypatch):
    app = serve.create_app(
        engine=make_engine("postgresql+psycopg://nobody:nobody@127.0.0.1:1/nope"),
        transit_for=lambda kek: FakeTransit())
    resp = TestClient(app).get("/health")
    assert resp.status_code == 503


def test_health_needs_no_token(keyservice_database_url, monkeypatch):
    app = _running_app(keyservice_database_url, monkeypatch, tokens={"tok": "svc"})
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200


def test_v1_path_without_token_is_401(keyservice_database_url, monkeypatch):
    app = _running_app(keyservice_database_url, monkeypatch, tokens={"tok": "svc"})
    with TestClient(app) as client:
        resp = client.get("/v1/anything")
    assert resp.status_code == 401
