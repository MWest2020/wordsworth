"""Read endpoint GET /documents/{id}/anonymized (add-anonymized-api).

Returns the stored, de-identified (pseudonymised) document text — the same text
that backs the index and the export ZIP, never clear PII. DB-backed (reads the
stored anonymized text), so these run in CI against a real Postgres and skip
locally without a DB — as the other DB integration tests do."""
from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.deletion import delete_document
from wordsworth.models import Document
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.supersession import supersede

PII_BSN = "123456782"
PII_EMAIL = "jan.jansen@haarlem.nl"


def _prepare(session_factory, mem_store, mem_index, fake_embedder, pdf):
    """Ingest+pseudonymise one PII doc; return its id (fully processed)."""
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        return doc.id


def _client(session_factory):
    return TestClient(create_app(session_factory=session_factory))


def test_anonymized_returns_pseudonymised_text(session_factory, mem_store,
                                               mem_index, fake_embedder,
                                               born_digital_pii_pdf):
    doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                      born_digital_pii_pdf)
    r = _client(session_factory).get(f"/documents/{doc_id}/anonymized")
    assert r.status_code == 200
    body = r.json()
    assert body["document_id"] == str(doc_id)
    text = body["anonymized_text"]
    assert text                                   # non-empty
    assert PII_BSN not in text                    # CARDINAL: never clear PII
    assert PII_EMAIL not in text
    assert "[BSN:" in text or "[EMAIL:" in text   # pseudonym tokens present


def test_unknown_document_is_404(session_factory):
    r = _client(session_factory).get(f"/documents/{uuid4()}/anonymized")
    assert r.status_code == 404


def test_not_deidentified_is_409(session_factory, mem_store, born_digital_pii_pdf):
    # Ingested but not processed → state exists, but no anonymized text yet.
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        doc_id = doc.id
    r = _client(session_factory).get(f"/documents/{doc_id}/anonymized")
    assert r.status_code == 409


def test_deleted_document_is_410_not_409(session_factory, mem_store, mem_index,
                                         fake_embedder, born_digital_pii_pdf):
    """Not yet de-identified tells a client to wait for something that will
    never come (deleted-document-answers-410, #456): a deletion is terminal,
    so a deleted document answers 410, not 409."""
    doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                      born_digital_pii_pdf)
    with session_factory() as s:
        delete_document(s, doc_id, mem_store, mem_index, actor="t")
        s.commit()
    r = _client(session_factory).get(f"/documents/{doc_id}/anonymized")
    assert r.status_code == 410
    assert r.json() == {"detail": "document deleted"}


def test_deleted_superseded_copy_is_410_not_409(session_factory, mem_store, mem_index,
                                                fake_embedder, born_digital_pii_pdf,
                                                born_digital_pdf):
    """Deleted wins over superseded (design.md decision 3): a deleted copy
    has no content whoever survives it, and naming the survivor would suggest
    the deleted copy's text is there."""
    survivor_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                           born_digital_pii_pdf)
    copy_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                       born_digital_pdf)
    with session_factory() as s:
        survivor = s.get(Document, survivor_id)
        supersede(s, copy_id, survivor_id, actor="t", as_object=survivor.object_key)
        s.commit()
    with session_factory() as s:
        delete_document(s, copy_id, mem_store, mem_index, actor="t")
        s.commit()
    r = _client(session_factory).get(f"/documents/{copy_id}/anonymized")
    assert r.status_code == 410
    assert r.json() == {"detail": "document deleted"}
    assert "superseded" not in r.text
    assert str(survivor_id) not in r.text
