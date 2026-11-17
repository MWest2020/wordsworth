# SPDX-License-Identifier: MIT
"""Every route with a document id in its path says what it answers after a
deletion (deleted-document-answers-410, design.md decision 6, task 3.2).

The structural walk (every `{document_id}` route has a row, and vice versa)
needs no database. The `410` and `record` rows are then checked against a
really-deleted document in Postgres, as a corpus reader; DB-backed, skips
without one.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from document_gone_inventory import missing_gone_rows, orphan_gone_rows
from document_gone_rows import ROWS
from inventory_app import full_app
from wordsworth.api import create_app
from wordsworth.deletion import delete_document
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer

KEYS = {"klezer": "lezer"}


def test_there_are_9_document_id_rows():
    assert len(ROWS) == 9


def test_every_document_id_route_has_a_row_and_every_row_a_route():
    app = full_app()
    assert missing_gone_rows(app) == set()
    assert orphan_gone_rows(app) == set()


def test_a_new_document_id_route_without_a_row_is_caught():
    """Shows the walk would catch a new per-document route merged without
    saying what it answers after a deletion, rather than restating what it
    walks."""
    app = full_app()

    @app.get("/documents/{document_id}/scratch")
    def scratch(document_id: str) -> dict:
        return {}

    assert ("GET", "/documents/{document_id}/scratch") in missing_gone_rows(app)


def _prepare_and_delete(session_factory, mem_store, mem_index, fake_embedder, pdf):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        doc_id = doc.id
    with session_factory() as s:
        delete_document(s, doc_id, mem_store, mem_index, actor="t")
        s.commit()
    return doc_id


def _client(session_factory, mem_store, mem_index):
    return TestClient(create_app(session_factory=session_factory, store=mem_store,
                                 search_index=mem_index, api_keys=KEYS,
                                 corpus_read_labels=["lezer"]))


REQUESTED = [r for r in ROWS if r.answer in ("410", "record")]


@pytest.mark.parametrize("row", REQUESTED, ids=[f"{r.method} {r.path}" for r in REQUESTED])
def test_a_deleted_document_answers_as_the_row_says(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf, row):
    doc_id = _prepare_and_delete(session_factory, mem_store, mem_index,
                                 fake_embedder, born_digital_pii_pdf)
    client = _client(session_factory, mem_store, mem_index)
    url = row.path.replace("{document_id}", str(doc_id))
    headers = {"X-API-Key": "klezer"}
    if row.method == "POST":
        resp = client.post(url, json={"kind": "fn", "type": "PERSON"}, headers=headers)
    else:
        resp = client.get(url, headers=headers)
    expected = 410 if row.answer == "410" else 200
    assert resp.status_code == expected, resp.text
