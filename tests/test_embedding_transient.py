# SPDX-License-Identifier: MIT
"""An Ollama instance going away is a blip, not a verdict (hoge-beschikbaarheid 3.2.1).

With two Ollama instances behind one Service, losing one mid-request is an
ordinary event. Until 2026-09-26 it failed the document: every embedding
failure was a plain `EmbeddingError`, and `retry.is_transient` read that as
permanent. The transport failures now say so; a bad embedding still does not
retry, because asking the same model again cannot fix it.
"""
from __future__ import annotations

import http.client
import io
import json
import urllib.error

import pytest

from wordsworth import embedder as emb
from wordsworth.embedder import EmbeddingError, EmbeddingUnavailable, OllamaEmbedder
from wordsworth.pipeline import ingest, process
from wordsworth.retry import is_transient
from wordsworth.states import State


def _failing(exc):
    def urlopen(*a, **k):
        raise exc
    return urlopen


def _answering(body: bytes):
    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return lambda *a, **k: _Resp(body)


def _http(code):
    return urllib.error.HTTPError("http://ollama/api/embeddings", code, "x", {}, None)


@pytest.mark.parametrize("cause", [
    urllib.error.URLError(ConnectionRefusedError("refused")),   # instance gone
    TimeoutError("timed out"),
    http.client.IncompleteRead(b"{"),                           # cut off mid-read
    http.client.RemoteDisconnected("closed"),
    _http(503),
])
def test_a_transport_failure_is_transient(monkeypatch, cause):
    monkeypatch.setattr(emb.urllib.request, "urlopen", _failing(cause))
    with pytest.raises(EmbeddingUnavailable) as caught:
        OllamaEmbedder("http://ollama", "bge-m3", 1024).embed(["tekst"])
    assert is_transient(caught.value)


@pytest.mark.parametrize("urlopen", [
    _failing(_http(404)),                                   # model not there: a bug
    _answering(b"not json"),
    _answering(json.dumps({"embedding": []}).encode()),     # empty: never a vector
    _answering(json.dumps({"embedding": [0.0, 0.0]}).encode()),
])
def test_a_bad_answer_stays_permanent(monkeypatch, urlopen):
    monkeypatch.setattr(emb.urllib.request, "urlopen", urlopen)
    with pytest.raises(EmbeddingError) as caught:
        OllamaEmbedder("http://ollama", "bge-m3", 1024).embed(["tekst"])
    assert not isinstance(caught.value, EmbeddingUnavailable)
    assert not is_transient(caught.value)


class _OneInstanceGone:
    """First call hits the instance that just went away; the retry the other."""

    dim = 64

    def __init__(self, inner):
        self.inner, self.calls = inner, 0

    def embed(self, texts):
        self.calls += 1
        if self.calls == 1:
            raise EmbeddingUnavailable("ollama embed failed: connection reset")
        return self.inner.embed(texts)


def test_a_lost_instance_no_longer_fails_the_document(
        session, born_digital_pii_pdf, mem_index, fake_embedder, mem_store, monkeypatch):
    monkeypatch.setenv("WORDSWORTH_RETRY_BASE_DELAY", "0")
    doc = ingest(session, mem_store, born_digital_pii_pdf)
    session.commit()
    embed = _OneInstanceGone(fake_embedder)
    assert process(session, doc.id, mem_store, search_index=mem_index,
                   embedder=embed) == State.INDEXED
    assert embed.calls == 2
