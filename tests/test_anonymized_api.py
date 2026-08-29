"""Read endpoint GET /documents/{id}/anonymized (add-anonymized-api).

Returns the stored, de-identified (pseudonymised) document text — the same text
that backs the index and the export ZIP, never clear PII. DB-backed (reads the
stored anonymized text), so these run in CI against a real Postgres and skip
locally without a DB — as the other DB integration tests do."""
from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore

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
