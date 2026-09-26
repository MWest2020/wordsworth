# SPDX-License-Identifier: MIT
"""A retry leaves a trace (hoge-beschikbaarheid, after 3.2.4).

On 2026-09-26 an Ollama instance was evicted under a probe and 327 of 327
queries were answered. Whether a retry had fired, or the dying instance was
simply never hit, could not be told: `retry_transient` said nothing. Now every
retry is a JSON line, and so is running out of retries.
"""
import json
import logging

import pytest

from wordsworth.embedder import EmbeddingError, EmbeddingUnavailable
from wordsworth.retry import retry_transient

#: What a message can carry: a fragment of the document it failed on.
SECRET = "Jan Jansen, Kerkstraat 12"


def _flaky(failures, exc):
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] <= failures:
            raise exc
        return "ok"
    return fn


def _lines(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records
            if r.name == "wordsworth.pipeline"]


def test_a_retry_that_succeeds_is_one_line(caplog):
    caplog.set_level(logging.WARNING, logger="wordsworth.pipeline")
    out = retry_transient(_flaky(1, EmbeddingUnavailable(SECRET)), 3, 0.5,
                          sleep=lambda s: None, what="query_embed")
    assert out == "ok"
    assert _lines(caplog) == [{"event": "retry", "what": "query_embed", "attempt": 1,
                               "of": 3, "error": "EmbeddingUnavailable",
                               "delay_s": 0.5, "level": "warning"}]


def test_running_out_of_retries_says_so(caplog):
    caplog.set_level(logging.WARNING, logger="wordsworth.pipeline")
    with pytest.raises(EmbeddingUnavailable):
        retry_transient(_flaky(9, EmbeddingUnavailable(SECRET)), 3, 0.5,
                        sleep=lambda s: None, what="embed")
    assert [(x["event"], x["attempt"], x["delay_s"]) for x in _lines(caplog)] == [
        ("retry", 1, 0.5), ("retry", 2, 1.0), ("retry_exhausted", 3, None)]
    assert caplog.records[-1].levelno == logging.ERROR


def test_a_permanent_error_is_not_a_retry(caplog):
    caplog.set_level(logging.WARNING, logger="wordsworth.pipeline")
    with pytest.raises(EmbeddingError):
        retry_transient(_flaky(9, EmbeddingError(SECRET)), 3, 0.5,
                        sleep=lambda s: None, what="embed")
    assert _lines(caplog) == []


def test_the_message_never_reaches_the_log(caplog):
    """The class, not the message: a message can quote the document."""
    caplog.set_level(logging.WARNING, logger="wordsworth.pipeline")
    with pytest.raises(EmbeddingUnavailable):
        retry_transient(_flaky(9, EmbeddingUnavailable(SECRET)), 2, 0,
                        sleep=lambda s: None, what="embed")
    assert _lines(caplog) and all(SECRET not in r.getMessage() for r in caplog.records)
