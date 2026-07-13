"""Tests for per-client rate limiting: token-bucket + API middleware."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.rate_limit import (
    EXEMPT_PATHS,
    InMemoryStore,
    TokenBucket,
)
from wordsworth.search_index import InMemoryIndex


class FakeClock:
    """Manually advanced monotonic clock, so refill is testable without sleep."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# --- Task 1.3: token-bucket behaviour --------------------------------------

def test_requests_within_limit_pass():
    bucket = TokenBucket(rate=1.0, burst=3, clock=FakeClock())
    for _ in range(3):
        assert bucket.check("client-a").allowed


def test_over_limit_is_rejected_with_retry_after():
    bucket = TokenBucket(rate=1.0, burst=2, clock=FakeClock())
    assert bucket.check("c").allowed
    assert bucket.check("c").allowed
    decision = bucket.check("c")
    assert not decision.allowed
    assert decision.retry_after >= 1


def test_bucket_refills_over_time():
    clock = FakeClock()
    bucket = TokenBucket(rate=1.0, burst=1, clock=clock)
    assert bucket.check("c").allowed
    assert not bucket.check("c").allowed  # empty now
    clock.advance(1.0)  # one token refills at 1/sec
    assert bucket.check("c").allowed


def test_clients_are_isolated_by_key():
    bucket = TokenBucket(rate=1.0, burst=1, clock=FakeClock())
    assert bucket.check("a").allowed
    assert bucket.check("b").allowed  # different key, own bucket


def test_invalid_config_is_a_hard_error():
    import pytest

    with pytest.raises(ValueError):
        TokenBucket(rate=0, burst=1)
    with pytest.raises(ValueError):
        TokenBucket(rate=1, burst=0)


def test_store_is_swappable_interface():
    store = InMemoryStore()
    bucket = TokenBucket(rate=1.0, burst=5, store=store, clock=FakeClock())
    bucket.check("c")
    assert store.get("c") is not None  # state persisted behind the interface


# --- Task 2.2: middleware over the API -------------------------------------

def _client_with_search(limiters):
    index = InMemoryIndex()
    index.index("d1", "parkeren in Haarlem", "k1")
    return TestClient(create_app(search_index=index, rate_limiters=limiters))


def test_429_with_retry_after_when_exceeded():
    limiters = {"/search": TokenBucket(rate=1.0, burst=1, clock=FakeClock())}
    client = _client_with_search(limiters)
    first = client.get("/search", params={"q": "parkeren"})
    assert first.status_code == 200
    second = client.get("/search", params={"q": "parkeren"})
    assert second.status_code == 429
    assert "Retry-After" in second.headers


def test_monitoring_endpoints_are_never_limited():
    # Even if /health is (mis)configured with a bucket, exemption wins.
    limiters = {"/health": TokenBucket(rate=1.0, burst=1, clock=FakeClock())}
    client = TestClient(create_app(rate_limiters=limiters))
    for _ in range(5):
        assert client.get("/health").status_code == 200
    assert EXEMPT_PATHS == frozenset({"/health", "/metrics"})


def test_rate_limiting_disabled_when_no_limiters():
    limiters: dict = {}
    client = _client_with_search(limiters)
    for _ in range(20):
        assert client.get("/search", params={"q": "parkeren"}).status_code == 200


def test_clients_isolated_over_http_by_api_key():
    limiters = {"/search": TokenBucket(rate=1.0, burst=1, clock=FakeClock())}
    client = _client_with_search(limiters)
    h1 = {"X-API-Key": "alice"}
    h2 = {"X-API-Key": "bob"}
    assert client.get("/search", params={"q": "x"}, headers=h1).status_code == 200
    assert client.get("/search", params={"q": "x"}, headers=h2).status_code == 200
    assert client.get("/search", params={"q": "x"}, headers=h1).status_code == 429
