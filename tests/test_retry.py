"""Bounded transient-retry helper — pure/local (pipeline-resilience)."""
from __future__ import annotations

import httpx
import pytest

from wordsworth.extraction import ExtractionError
from wordsworth.openanonymiser_driver import AnonymizationEngineError
from wordsworth.retry import is_transient, retry_transient


def test_succeeds_after_transient_failures_with_backoff():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise AnonymizationEngineError("blip")
        return "ok"

    slept: list[float] = []
    assert retry_transient(fn, 3, 0.5, sleep=slept.append) == "ok"
    assert calls["n"] == 3
    assert slept == [0.5, 1.0]  # exponential backoff, injected sleep (no real wait)


def test_raises_after_exhausting_attempts():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise AnonymizationEngineError("down")

    with pytest.raises(AnonymizationEngineError):
        retry_transient(fn, 3, 0.0, sleep=lambda _s: None)
    assert calls["n"] == 3  # exactly `attempts` tries


def test_permanent_error_is_not_retried():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise ValueError("bad input")

    with pytest.raises(ValueError):
        retry_transient(fn, 5, 0.0, sleep=lambda _s: None)
    assert calls["n"] == 1  # permanent → immediate, no retry


def _http_status(code: int) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "http://x")
    return httpx.HTTPStatusError("x", request=req, response=httpx.Response(code))


def test_is_transient_classification():
    assert is_transient(AnonymizationEngineError("x"))     # service unreachable
    assert is_transient(httpx.ConnectError("x"))
    assert is_transient(TimeoutError())
    assert is_transient(ConnectionError())
    assert is_transient(_http_status(503))                 # 5xx transient
    assert not is_transient(_http_status(400))             # 4xx is a bug
    assert not is_transient(ValueError("x"))
    assert not is_transient(ExtractionError("x"))


def test_opensearch_style_connection_error_is_transient_by_name():
    class OpenSearchConnectionError(Exception):
        pass

    class TransportTimeout(Exception):
        pass

    assert is_transient(OpenSearchConnectionError())
    assert is_transient(TransportTimeout())
    assert not is_transient(RuntimeError("unrelated"))
