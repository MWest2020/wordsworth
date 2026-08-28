"""Opt-in CORS for browser frontends (e.g. the Wordsworth Console).

Uses /search (InMemoryIndex, no DB) as a protected route. CORS is off unless
origins are configured; when on, preflight is answered before auth so a browser
can call the API cross-origin while X-API-Key still governs the actual request.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.search_index import InMemoryIndex

ORIGIN = "https://mwest2020.github.io"


def _app(**kw) -> TestClient:
    return TestClient(create_app(search_index=InMemoryIndex(), rate_limiters={}, **kw))


def test_cors_off_by_default():
    # No origins configured → no Access-Control-Allow-Origin header (unchanged).
    r = _app().get("/search", params={"q": "x"}, headers={"Origin": ORIGIN})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_cors_allows_configured_origin():
    r = _app(cors_allow_origins=[ORIGIN]).get(
        "/search", params={"q": "x"}, headers={"Origin": ORIGIN})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == ORIGIN


def test_cors_omits_header_for_unlisted_origin():
    r = _app(cors_allow_origins=[ORIGIN]).get(
        "/search", params={"q": "x"}, headers={"Origin": "https://evil.example"})
    # Request still served, but the browser gets no allow-origin → it blocks.
    assert r.headers.get("access-control-allow-origin") is None


def test_preflight_answered_before_auth():
    # OPTIONS preflight must succeed even when auth is on and no key is sent —
    # CORS is outermost, so it short-circuits before the auth middleware.
    r = _app(cors_allow_origins=[ORIGIN], api_keys={"sk_v": "alice"}).options(
        "/grants",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-api-key,content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == ORIGIN
    assert "POST" in r.headers.get("access-control-allow-methods", "")


def test_actual_call_still_needs_key_with_cors():
    # CORS permits the origin; it is not authentication. A real (non-preflight)
    # request without a valid key is still rejected.
    r = _app(cors_allow_origins=[ORIGIN], api_keys={"sk_v": "alice"}).get(
        "/search", params={"q": "x"}, headers={"Origin": ORIGIN})
    assert r.status_code == 401
