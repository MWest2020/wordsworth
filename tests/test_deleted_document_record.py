# SPDX-License-Identifier: MIT
"""GET /documents/{id}/state and GET /documents/{id} keep answering for a
deleted document: the default of #501 (deleted-document-answers-410,
design.md decision 2, task 3.1). They show what a deletion keeps -- the row
and the trail -- never the content it removed.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.deletion import delete_document
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer

PII_BSN = "123456782"
PII_IBAN = "NL91ABNA0417164300"
PII_EMAIL = "jan.jansen@haarlem.nl"
FILENAME = "aanvraag-janssen.pdf"


def _prepare_and_delete(session_factory, mem_store, mem_index, fake_embedder, pdf):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, pdf, filename=FILENAME)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        doc_id = doc.id
    with session_factory() as s:
        delete_document(s, doc_id, mem_store, mem_index, actor="opruimer")
        s.commit()
    return doc_id


def _client(session_factory):
    return TestClient(create_app(session_factory=session_factory))


def test_the_state_of_a_deleted_document(session_factory, mem_store, mem_index,
                                         fake_embedder, born_digital_pii_pdf):
    doc_id = _prepare_and_delete(session_factory, mem_store, mem_index,
                                 fake_embedder, born_digital_pii_pdf)
    r = _client(session_factory).get(f"/documents/{doc_id}/state")
    assert r.status_code == 200
    assert r.json()["state"] == "deleted"


def test_the_trail_of_a_deleted_document(session_factory, mem_store, mem_index,
                                         fake_embedder, born_digital_pii_pdf):
    doc_id = _prepare_and_delete(session_factory, mem_store, mem_index,
                                 fake_embedder, born_digital_pii_pdf)
    r = _client(session_factory).get(f"/documents/{doc_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "deleted"

    steps = body["steps"]
    assert steps[-1]["step"] == "delete"
    assert steps[-1]["to_state"] == "deleted"
    assert steps[-1]["payload"]["actor"] == "opruimer"
    assert "object" in steps[-1]["payload"]            # the counts

    text = r.text
    assert PII_BSN not in text and PII_IBAN not in text and PII_EMAIL not in text
    assert "[BSN:" not in text and "[IBAN:" not in text and "[EMAIL:" not in text
    assert FILENAME not in text
