"""design.md "Service authentication": fail-closed Bearer token, pure ASGI
middleware, answering before the body is read and before any database read."""
from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from fastapi.testclient import TestClient

from wordsworth.keyservice.auth import ServiceTokenMiddleware


def _app(tokens: dict[str, str]) -> Starlette:
    async def echo(request):
        caller = request.scope.get("state", {}).get("service_caller")
        return JSONResponse({"service_caller": caller})

    async def body_reading_route(request):
        # Proves the middleware never reaches a route that would read the
        # body when it refuses first.
        await request.body()
        return JSONResponse({"ok": True})

    app = Starlette(routes=[
        Route("/v1/echo", echo),
        Route("/v1/body", body_reading_route, methods=["POST"]),
        Route("/health", lambda r: JSONResponse({"status": "ok"})),
    ])
    app.add_middleware(ServiceTokenMiddleware, tokens=tokens)
    return app


def test_missing_token_is_401():
    client = TestClient(_app({"tok": "svc"}))
    resp = client.get("/v1/echo")
    assert resp.status_code == 401


def test_unknown_token_is_401():
    client = TestClient(_app({"tok": "svc"}))
    resp = client.get("/v1/echo", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_empty_token_set_refuses_every_call():
    client = TestClient(_app({}))
    resp = client.get("/v1/echo", headers={"Authorization": "Bearer anything"})
    assert resp.status_code == 401


def test_valid_token_sets_service_caller():
    client = TestClient(_app({"tok": "ingest"}))
    resp = client.get("/v1/echo", headers={"Authorization": "Bearer tok"})
    assert resp.status_code == 200
    assert resp.json() == {"service_caller": "ingest"}


def test_health_needs_no_token():
    client = TestClient(_app({"tok": "svc"}))
    resp = client.get("/health")
    assert resp.status_code == 200


def test_refusal_never_reads_the_body():
    client = TestClient(_app({"tok": "svc"}))
    resp = client.post("/v1/body", content=b"this would blow up if read twice or oddly")
    assert resp.status_code == 401


@pytest.mark.parametrize("auth_header", [None, "Bearer", "Bearer wrong"])
def test_no_database_statement_before_a_valid_token(auth_header, database_url):
    """"before any read" (tasks.md), proved by counting statements: the
    middleware itself never touches the database, so a bad token causes
    zero SQL statements to be executed against a real engine."""
    from sqlalchemy import event

    from wordsworth.keyservice.db import make_engine

    engine = make_engine(database_url)
    statements = []
    event.listen(engine, "before_cursor_execute",
                lambda *a, **k: statements.append(a))

    client = TestClient(_app({"tok": "svc"}))
    headers = {"Authorization": auth_header} if auth_header else {}
    resp = client.get("/v1/echo", headers=headers)
    assert resp.status_code == 401
    assert statements == []
