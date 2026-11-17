# SPDX-License-Identifier: MIT
"""The caller gate and request validation hold for a deleted document exactly
as they do for any other (deleted-document-answers-410, design.md decision 3,
tasks 2.4 and 2.5): a caller the gate refuses learns nothing about the
document, and a malformed request is refused before the 404/410 the document
itself would get. DB-backed: skips without a Postgres.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth.api import create_app
from wordsworth.deletion import delete_document
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer

KEYS = {"klezer": "lezer", "kderde": "derde"}
UNKNOWN_ID = "11111111-1111-1111-1111-111111111111"
CORPUS_READ = {"detail": "caller not authorized for corpus read"}
ROUTES = [
    ("GET", "/documents/{id}/anonymized"),
    ("GET", "/documents/{id}/redacted.pdf"),
    ("POST", "/documents/{id}/feedback"),
]


def _prepare(session_factory, mem_store, mem_index, fake_embedder, pdf):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        return doc.id


def _client(session_factory, mem_store):
    return TestClient(create_app(session_factory=session_factory, store=mem_store,
                                 api_keys=KEYS, corpus_read_labels=["lezer"]))


def _request(client, method, path, doc_id, *, label="lezer", **kw):
    url = path.replace("{id}", str(doc_id))
    headers = {"X-API-Key": "klezer" if label == "lezer" else "kderde"}
    if method == "POST":
        return client.post(url, json=kw.get("json", {"kind": "fn", "type": "PERSON"}),
                           headers=headers)
    return client.get(url, headers=headers, params=kw.get("params"))


def _doc_id(session_factory, mem_store, mem_index, fake_embedder, pdf, which):
    if which == "unknown":
        return UNKNOWN_ID
    doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder, pdf)
    if which == "deleted":
        with session_factory() as s:
            delete_document(s, doc_id, mem_store, mem_index, actor="t")
            s.commit()
    return doc_id


@pytest.mark.parametrize("method,path", ROUTES, ids=[f"{m} {p}" for m, p in ROUTES])
@pytest.mark.parametrize("which", ["deleted", "live", "unknown"])
def test_a_caller_without_corpus_read_learns_nothing(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf,
        method, path, which):
    doc_id = _doc_id(session_factory, mem_store, mem_index, fake_embedder,
                     born_digital_pii_pdf, which)
    r = _request(_client(session_factory, mem_store), method, path, doc_id,
                label="derde")
    assert r.status_code == 403
    assert r.json() == CORPUS_READ


@pytest.mark.parametrize("method,path", ROUTES, ids=[f"{m} {p}" for m, p in ROUTES])
def test_an_unknown_id_is_still_unknown(session_factory, mem_store, method, path):
    r = _request(_client(session_factory, mem_store), method, path, UNKNOWN_ID)
    assert r.status_code == 404


@pytest.mark.parametrize("which", ["deleted", "live", "unknown"])
def test_an_unsupported_view_is_400_not_410_and_not_404(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf, which):
    doc_id = _doc_id(session_factory, mem_store, mem_index, fake_embedder,
                     born_digital_pii_pdf, which)
    r = _request(_client(session_factory, mem_store), "GET",
                "/documents/{id}/anonymized", doc_id, params={"view": "nonsense"})
    assert r.status_code == 400


@pytest.mark.parametrize("method,path", ROUTES, ids=[f"{m} {p}" for m, p in ROUTES])
def test_a_malformed_id_is_422(session_factory, mem_store, method, path):
    r = _request(_client(session_factory, mem_store), method, path, "not-a-uuid")
    assert r.status_code == 422


@pytest.mark.parametrize("which", ["deleted", "live"])
def test_an_invalid_feedback_body_is_422_and_writes_nothing(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf, which):
    doc_id = _doc_id(session_factory, mem_store, mem_index, fake_embedder,
                     born_digital_pii_pdf, which)
    with session_factory() as s:
        before = len(s.execute(select(AuditRecord)
                               .where(AuditRecord.document_id == doc_id)).scalars().all())

    r = _request(_client(session_factory, mem_store), "POST",
                "/documents/{id}/feedback", doc_id,
                json={"kind": "bogus", "type": "PERSON"})
    assert r.status_code == 422

    with session_factory() as s:
        after = len(s.execute(select(AuditRecord)
                              .where(AuditRecord.document_id == doc_id)).scalars().all())
    assert after == before
