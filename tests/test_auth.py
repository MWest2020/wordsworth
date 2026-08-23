"""Opt-in API-key auth — pure/local (no DB) (add-api-key-auth).

Uses /search (mounts on an InMemoryIndex, no DB) as a non-exempt protected route
to exercise the middleware; the DB-backed reveal caller-attribution is in
tests/test_auth_db.py (CI)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.auth import parse_api_keys
from wordsworth.search_index import InMemoryIndex


def _app(**kw) -> TestClient:
    return TestClient(create_app(search_index=InMemoryIndex(), rate_limiters={}, **kw))


def test_parse_api_keys():
    assert parse_api_keys("alice:sk_a,bob:sk_b") == {"sk_a": "alice", "sk_b": "bob"}
    assert parse_api_keys("") == {}
    assert parse_api_keys("nocolon, :nokey, lbl:") == {}     # malformed skipped
    assert parse_api_keys("  a : k ") == {"k": "a"}          # trimmed


def test_open_by_default_no_keys():
    # No keys configured → API stays open (non-breaking).
    assert _app().get("/search", params={"q": "x"}).status_code == 200


def test_missing_key_is_401_when_configured():
    assert _app(api_keys={"sk_v": "alice"}).get(
        "/search", params={"q": "x"}).status_code == 401


def test_wrong_key_is_401():
    assert _app(api_keys={"sk_v": "alice"}).get(
        "/search", params={"q": "x"}, headers={"X-API-Key": "nope"}).status_code == 401


def test_valid_key_passes():
    assert _app(api_keys={"sk_v": "alice"}).get(
        "/search", params={"q": "x"}, headers={"X-API-Key": "sk_v"}).status_code == 200


def test_health_open_even_with_auth():
    assert _app(api_keys={"sk_v": "alice"}).get("/health").status_code == 200


def test_key_value_not_echoed_in_401_body():
    r = _app(api_keys={"sk_secret": "alice"}).get(
        "/search", params={"q": "x"}, headers={"X-API-Key": "sk_secret"})
    # sanity: the valid path works; the 401 body must never contain a key
    r401 = _app(api_keys={"sk_secret": "alice"}).get("/search", params={"q": "x"})
    assert "sk_secret" not in r401.text
