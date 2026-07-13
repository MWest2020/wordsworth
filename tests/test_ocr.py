import pytest
from sqlalchemy import func, select

from wordsworth.models import AuditRecord
from wordsworth.ocr import FixedOcrEngine, OcrEngine, OcrError
from wordsworth.pipeline import current_state, process, register
from wordsworth.recovery import recover
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


def test_engine_failure_raises_not_silent():
    class Boom:
        lang = "nld"

        def ocr(self, pdf_bytes: bytes) -> str:
            raise OcrError("engine down")

    with pytest.raises(OcrError):
        Boom().ocr(b"%PDF-1.4")


# --- recovery flow ----------------------------------------------------------

def _park_as_unprocessable(session, scanned_pdf):
    doc = register(session, "scan.pdf")
    assert process(session, doc.id, scanned_pdf) == State.UNPROCESSABLE_OCR
    session.commit()
    return doc


def _audit_count(session, document_id) -> int:
    return session.execute(
        select(func.count()).select_from(AuditRecord)
        .where(AuditRecord.document_id == document_id)
    ).scalar_one()


def test_ocr_yields_usable_text_becomes_extractable(session, scanned_pdf):
    doc = _park_as_unprocessable(session, scanned_pdf)
    before = _audit_count(session, doc.id)

    # Injected LOCAL engine drives the text — no cloud call is made.
    final = recover(session, doc.id, scanned_pdf, threshold=10,
                    engine=FixedOcrEngine("Herstelde tekst uit een scan. " * 3))
    session.commit()

    assert final == State.EXTRACTABLE
    assert current_state(session, doc.id) == State.EXTRACTABLE
    last = session.execute(
        select(AuditRecord).where(AuditRecord.document_id == doc.id)
        .order_by(AuditRecord.seq.desc()).limit(1)
    ).scalar_one()
    assert last.step == "ocr" and last.to_state == "extractable"
    assert _audit_count(session, doc.id) == before + 1


def test_ocr_yields_too_little_text_stays_unprocessable(session, scanned_pdf):
    doc = _park_as_unprocessable(session, scanned_pdf)
    before = _audit_count(session, doc.id)

    final = recover(session, doc.id, scanned_pdf, threshold=10,
                    engine=FixedOcrEngine("kort"))  # < 10 chars for the 1 page
    session.commit()

    assert final == State.UNPROCESSABLE_OCR
    assert current_state(session, doc.id) == State.UNPROCESSABLE_OCR
    assert _audit_count(session, doc.id) == before  # no transition, no record


def test_recovery_engine_failure_leaves_document_untouched(session, scanned_pdf):
    doc = _park_as_unprocessable(session, scanned_pdf)
    before = _audit_count(session, doc.id)

    class Boom:
        lang = "nld"

        def ocr(self, pdf_bytes: bytes) -> str:
            raise OcrError("tesseract crashed")

    with pytest.raises(OcrError):
        recover(session, doc.id, scanned_pdf, engine=Boom())
    session.rollback()

    assert current_state(session, doc.id) == State.UNPROCESSABLE_OCR
    assert _audit_count(session, doc.id) == before  # no silent skip, no partial write


def test_recover_only_applies_to_unprocessable(session, born_digital_pdf):
    doc = register(session, "born.pdf")
    session.commit()  # still REGISTERED
    with pytest.raises(ValueError):
        recover(session, doc.id, born_digital_pdf, engine=FixedOcrEngine("x"))
