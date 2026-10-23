import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from wordsworth import recovery
from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.api import create_app
from wordsworth.extraction import extract_text
from wordsworth.models import AuditRecord, Document
from wordsworth.ocr import FixedOcrEngine, OcrEngine, OcrError
from wordsworth.pipeline import current_state, ingest, process
from wordsworth.recovery import recover
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import TERMINAL, State, is_allowed


# --- state machine: unprocessable_ocr gains one outgoing edge ---------------

def test_unprocessable_ocr_is_no_longer_terminal():
    assert State.UNPROCESSABLE_OCR not in TERMINAL


def test_ocr_recovery_edge_allowed():
    assert is_allowed(State.UNPROCESSABLE_OCR, State.EXTRACTABLE)


def test_no_other_edge_out_of_unprocessable_ocr():
    # Recovery is the ONLY way out; it cannot skip straight to indexed etc.
    for target in (State.EXTRACTED, State.ANONYMIZED, State.INDEXED, State.FAILED):
        assert not is_allowed(State.UNPROCESSABLE_OCR, target)


# --- the seam: local engine injected, no cloud ------------------------------

def test_fixed_engine_satisfies_protocol():
    assert isinstance(FixedOcrEngine("x"), OcrEngine)


def test_engine_output_is_pdf_with_extractable_text_layer():
    # The contract: OCR returns a text-layer PDF, never raw text. The normal
    # pypdf extraction path must be able to read that layer.
    out = FixedOcrEngine("Herstelde tekst uit een scan.").ocr(b"%PDF-1.4")
    assert isinstance(out, bytes) and out.startswith(b"%PDF")
    assert "Herstelde tekst uit een scan." in extract_text(out)


def test_engine_failure_raises_not_silent():
    class Boom:
        lang = "nld"

        def ocr(self, pdf_bytes: bytes) -> bytes:
            raise OcrError("engine down")

    with pytest.raises(OcrError):
        Boom().ocr(b"%PDF-1.4")


# --- recovery flow ----------------------------------------------------------

def _park_as_unprocessable(session, store, scanned_pdf):
    doc = ingest(session, store, scanned_pdf)
    assert process(session, doc.id, store) == State.UNPROCESSABLE_OCR
    session.commit()
    return doc


def _audit_count(session, document_id) -> int:
    return session.execute(
        select(func.count()).select_from(AuditRecord)
        .where(AuditRecord.document_id == document_id)
    ).scalar_one()


def _last_record(session, document_id) -> AuditRecord:
    return session.execute(
        select(AuditRecord).where(AuditRecord.document_id == document_id)
        .order_by(AuditRecord.seq.desc()).limit(1)
    ).scalar_one()


def test_ocr_yields_usable_text_becomes_extractable_and_indexes_ocr_text(
    session, scanned_pdf, mem_store, mem_index, fake_embedder,
):
    doc = _park_as_unprocessable(session, mem_store, scanned_pdf)
    scan_key = doc.object_key
    before = _audit_count(session, doc.id)

    # Injected LOCAL engine drives the text — no cloud call is made.
    final = recover(session, doc.id, mem_store, threshold=10,
                    engine=FixedOcrEngine("Herstelde tekst uit een scan. " * 3))
    session.commit()

    assert final == State.EXTRACTABLE
    assert current_state(session, doc.id) == State.EXTRACTABLE
    # The OCR'd text-layer PDF lives under its OWN content-addressed key;
    # object_key points at it and the original scan object is kept.
    new_key = session.get(Document, doc.id).object_key
    assert new_key != scan_key
    assert new_key == "documents/" + hashlib.sha256(mem_store.get(new_key)).hexdigest()
    assert mem_store.get(scan_key) == scanned_pdf
    last = _last_record(session, doc.id)
    assert last.step == "ocr" and last.to_state == "extractable"
    assert last.payload["old_object_key"] == scan_key
    assert last.payload["new_object_key"] == new_key
    assert _audit_count(session, doc.id) == before + 1

    # The recovered document flows the FULL extract -> anonymize -> index path
    # and the indexed content is the OCR text layer, not the empty scan.
    assert process(session, doc.id, mem_store, search_index=mem_index,
                   embedder=fake_embedder) == State.INDEXED
    session.commit()
    hits = mem_index.search("Herstelde tekst")
    assert [h.document_id for h in hits] == [str(doc.id)]
    indexed_text, _key, _vec = mem_index._docs[str(doc.id)]
    assert "Herstelde tekst uit een scan." in indexed_text


def test_ocr_yields_too_little_text_stays_unprocessable_but_is_audited(
    session, scanned_pdf, mem_store,
):
    doc = _park_as_unprocessable(session, mem_store, scanned_pdf)
    scan_key = doc.object_key
    before = _audit_count(session, doc.id)

    final = recover(session, doc.id, mem_store, threshold=10,
                    engine=FixedOcrEngine("kort"))  # < 10 chars for the 1 page
    session.commit()

    assert final == State.UNPROCESSABLE_OCR
    assert current_state(session, doc.id) == State.UNPROCESSABLE_OCR
    assert session.get(Document, doc.id).object_key == scan_key  # not repointed
    # NOT a silent no-op: the attempt itself is an access-style audit record.
    assert _audit_count(session, doc.id) == before + 1
    last = _last_record(session, doc.id)
    assert last.step == "ocr"
    assert last.from_state == "unprocessable_ocr" and last.to_state == "unprocessable_ocr"
    assert last.payload["chars"] == len("kort") and last.payload["pages"] == 1


def test_recovery_engine_failure_leaves_document_untouched(
    session, scanned_pdf, mem_store,
):
    doc = _park_as_unprocessable(session, mem_store, scanned_pdf)
    before = _audit_count(session, doc.id)

    class Boom:
        lang = "nld"

        def ocr(self, pdf_bytes: bytes) -> bytes:
            raise OcrError("tesseract crashed")

    with pytest.raises(OcrError):
        recover(session, doc.id, mem_store, engine=Boom())
    session.rollback()

    assert current_state(session, doc.id) == State.UNPROCESSABLE_OCR
    assert _audit_count(session, doc.id) == before  # no silent skip, no partial write


def test_recover_only_applies_to_unprocessable(session, born_digital_pdf, mem_store):
    doc = ingest(session, mem_store, born_digital_pdf)
    session.commit()  # still REGISTERED
    with pytest.raises(ValueError):
        recover(session, doc.id, mem_store, engine=FixedOcrEngine("x"))


# --- a document without text is never indexed silently (ingest-records-source) --

def test_no_text_layer_and_no_ocr_text_ends_visible_and_unindexed(
    session_factory, scanned_pdf, mem_store, fake_embedder, monkeypatch,
):
    """A scan OCR cannot read: the full /ingest straat parks the document in
    `unprocessable_ocr` — never indexed as empty text — and the API shows it."""
    monkeypatch.setattr(recovery, "_default_ocr_engine", lambda: FixedOcrEngine(""))
    index = InMemoryIndex()
    c = TestClient(create_app(session_factory=session_factory, store=mem_store,
                              search_index=index, embedder=fake_embedder,
                              anonymizer=DeterministicAnonymizer()))

    r = c.post("/ingest", params={"dossier": "Z"},
               files={"files": ("scan.pdf", scanned_pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    document_id = r.json()["results"][0]["document_id"]
    assert r.json()["results"][0]["state"] == "unprocessable_ocr"
    assert r.json()["indexed"] == 0

    state_resp = c.get(f"/documents/{document_id}/state")
    assert state_resp.json()["state"] == "unprocessable_ocr"
    meta_resp = c.get(f"/documents/{document_id}")
    assert meta_resp.json()["state"] == "unprocessable_ocr"

    assert index._docs == {}
