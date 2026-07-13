"""Opt-in OCR recovery: the one outgoing edge from `unprocessable_ocr`.

Runs AFTER the born-digital pass, so it never delays that path. It depends on
the ``OcrEngine`` protocol (never a concrete engine) and reuses the profiling
threshold, so a recovered document rejoins the ordinary extract -> anonymize ->
index flow. OCR engine failure raises (OcrError) and nothing commits — the
document stays `unprocessable_ocr` for retry, never silently dropped."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from .config import settings
from .ocr import OcrEngine
from .pipeline import current_state, transition
from .profiling import profile_pdf
from .states import State


def _default_ocr_engine() -> OcrEngine:
    from .ocr import TesseractEngine

    return TesseractEngine.from_config()


def recover(
    session: Session,
    document_id: UUID,
    pdf_bytes: bytes,
    threshold: int | None = None,
    engine: OcrEngine | None = None,
) -> State:
    """OCR one `unprocessable_ocr` document and re-classify it.

    OCR the scanned PDF, then re-apply the SAME characters-per-page threshold as
    profiling (page count re-derived from the source, chars from the OCR text):
    at/above -> `extractable` (transition recorded in the audit trail); below ->
    it stays `unprocessable_ocr` (no transition, no record).
    """
    threshold = threshold if threshold is not None else settings.born_digital_threshold
    engine = engine or _default_ocr_engine()
    state = current_state(session, document_id)
    if state != State.UNPROCESSABLE_OCR:
        raise ValueError(f"OCR recovery only applies to unprocessable_ocr, not {state}")
    text = engine.ocr(pdf_bytes)  # OcrError propagates: loud, retryable, no skip
    pages = profile_pdf(pdf_bytes, threshold)["pages"]
    chars = len((text or "").strip())
    if pages <= 0 or chars < threshold * pages:
        return State.UNPROCESSABLE_OCR  # too little text -> unchanged
    transition(session, document_id, State.EXTRACTABLE, step="ocr",
               payload={"chars": chars, "pages": pages})
    return State.EXTRACTABLE
