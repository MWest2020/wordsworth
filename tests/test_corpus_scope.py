"""Opt-in corpus-read scope (F4 mitigation): which caller labels may read full
de-identified document text (/documents/{id}/anonymized + /export/anonymized.zip).

Pure decision logic + a no-DB 403 short-circuit run locally; the authorized-path
(200 on a real document) is DB-backed and runs in CI.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.auth import authorize_corpus_read
from wordsworth.search_index import InMemoryIndex


# ---- pure decision logic (local) ----

def test_scope_off_allows_anyone():
    assert authorize_corpus_read(None, []) is True
    assert authorize_corpus_read("anyone", []) is True


def test_scope_on_allows_only_listed():
    assert authorize_corpus_read("cli", ["cli", "console"]) is True
    assert authorize_corpus_read("console", ["cli", "console"]) is True
    assert authorize_corpus_read("test", ["cli", "console"]) is False


def test_scope_on_denies_none_caller_fail_closed():
    assert authorize_corpus_read(None, ["cli"]) is False


# ---- endpoint 403 short-circuits before any DB access (local, no DB) ----

def _boom_session_factory():
    raise AssertionError("session must not be touched when the scope denies")


def _client(**kw):
    return TestClient(create_app(session_factory=_boom_session_factory,
                                 search_index=InMemoryIndex(), rate_limiters={}, **kw))


def test_anonymized_denied_for_unlisted_caller():
    c = _client(api_keys={"k": "reader"}, corpus_read_labels=["exporter"])
    r = c.get(f"/documents/{uuid4()}/anonymized", headers={"X-API-Key": "k"})
    assert r.status_code == 403


def test_export_denied_for_unlisted_caller():
    c = _client(api_keys={"k": "reader"}, corpus_read_labels=["exporter"])
    r = c.get("/export/anonymized.zip", headers={"X-API-Key": "k"})
    assert r.status_code == 403


# ---- authorized path reaches the data (DB-backed, CI) ----

def test_anonymized_allowed_for_listed_caller(session_factory, mem_store, mem_index,
                                              fake_embedder, born_digital_pii_pdf):
    from wordsworth.keys import InMemoryKeyProvider
    from wordsworth.mapping_store import PostgresMappingStore
    from wordsworth.pipeline import ingest, process
    from wordsworth.pseudonymizer import Pseudonymizer
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
    c = TestClient(create_app(session_factory=session_factory, key_provider=kp,
                              api_keys={"ok": "exporter", "no": "reader"},
                              corpus_read_labels=["exporter"]))
    ok = c.get(f"/documents/{doc.id}/anonymized", headers={"X-API-Key": "ok"})
    assert ok.status_code == 200 and "[" in ok.json()["anonymized_text"]
    denied = c.get(f"/documents/{doc.id}/anonymized", headers={"X-API-Key": "no"})
    assert denied.status_code == 403
