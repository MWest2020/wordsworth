"""A document records where it came from (ingest-records-source).

The three tests design.md asks for: fields reach the document row AND the
ingest audit record; omitting them changes nothing except that
`source_sha256` is still recorded; a malformed `source_url` is refused with a
reason and ingests nothing. Test 4 (no text, no index entry) lives in
test_ocr.py, next to the rest of the OCR-recovery behaviour it pins.
"""
from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.api import create_app
from wordsworth.models import AuditRecord, Document
from wordsworth.search_index import InMemoryIndex


def _client(session_factory, mem_store, fake_embedder, index=None):
    return TestClient(create_app(
        session_factory=session_factory, store=mem_store,
        search_index=index or InMemoryIndex(), embedder=fake_embedder,
        anonymizer=DeterministicAnonymizer()))


def test_provenance_reaches_the_document_and_the_audit_record(
    session_factory, born_digital_pdf, mem_store, fake_embedder,
):
    c = _client(session_factory, mem_store, fake_embedder)
    r = c.post(
        "/ingest",
        params={"dossier": "Z", "source_url": "https://example.org/besluit.pdf",
               "fetched_at": "2026-10-23T10:00:00+00:00"},
        files={"files": ("a.pdf", born_digital_pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    document_id = r.json()["results"][0]["document_id"]
    digest = hashlib.sha256(born_digital_pdf).hexdigest()

    with session_factory() as s:
        doc = s.get(Document, document_id)
        assert doc.source_url == "https://example.org/besluit.pdf"
        assert doc.fetched_at.isoformat() == "2026-10-23T10:00:00+00:00"
        assert doc.source_sha256 == digest

        record = s.execute(
            select(AuditRecord).where(AuditRecord.document_id == document_id,
                                      AuditRecord.step == "register")
        ).scalar_one()
        assert record.payload["source_url"] == "https://example.org/besluit.pdf"
        assert record.payload["fetched_at"] == "2026-10-23T10:00:00+00:00"
        assert record.payload["source_sha256"] == digest


def test_omitting_provenance_leaves_ingest_unchanged(
    session_factory, born_digital_pdf, mem_store, fake_embedder,
):
    c = _client(session_factory, mem_store, fake_embedder)
    r = c.post("/ingest", params={"dossier": "Z"},
               files={"files": ("a.pdf", born_digital_pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    document_id = r.json()["results"][0]["document_id"]
    digest = hashlib.sha256(born_digital_pdf).hexdigest()

    with session_factory() as s:
        doc = s.get(Document, document_id)
        assert doc.source_url is None
        assert doc.fetched_at is None
        assert doc.source_sha256 == digest  # always recorded, request or no

        record = s.execute(
            select(AuditRecord).where(AuditRecord.document_id == document_id,
                                      AuditRecord.step == "register")
        ).scalar_one()
        assert "source_url" not in record.payload
        assert "fetched_at" not in record.payload
        assert record.payload["source_sha256"] == digest


def test_malformed_source_url_is_refused_and_nothing_is_ingested(
    session_factory, born_digital_pdf, mem_store, fake_embedder,
):
    c = _client(session_factory, mem_store, fake_embedder)
    with session_factory() as s:
        before = s.execute(select(func.count()).select_from(Document)).scalar_one()

    r = c.post("/ingest", params={"dossier": "Z", "source_url": "ftp://x"},
               files={"files": ("a.pdf", born_digital_pdf, "application/pdf")})
    assert r.status_code == 400
    assert "source_url" in r.json()["detail"]

    r = c.post("/ingest", params={"dossier": "Z", "source_url": "https://"},
               files={"files": ("a.pdf", born_digital_pdf, "application/pdf")})
    assert r.status_code == 400

    r = c.post("/ingest", params={"dossier": "Z",
                                 "source_url": "https://example.org/x",
                                 "fetched_at": "2026-10-23T10:00:00"},  # no tz
               files={"files": ("a.pdf", born_digital_pdf, "application/pdf")})
    assert r.status_code == 400
    assert "fetched_at" in r.json()["detail"]

    with session_factory() as s:
        after = s.execute(select(func.count()).select_from(Document)).scalar_one()
    assert after == before
