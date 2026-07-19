"""Opt-in OCR recovery: the one outgoing edge from `unprocessable_ocr`.

Runs AFTER the born-digital pass, so it never delays that path. It depends on
the ``OcrEngine`` protocol (never a concrete engine): the engine returns a
text-layer PDF, which is stored via the ``ObjectStore`` seam under its OWN
content-addressed key (overwriting the scan's key would break key ==
sha256(bytes) and destroy the source scan), and `documents.object_key` is
repointed at it — so a recovered document rejoins the ordinary extract ->
anonymize -> index flow with no OCR-specific branch. Every attempt is audited:
a recovering one as the `unprocessable_ocr -> extractable` transition (payload
carries old+new object keys), a non-recovering one as an access-style record
(from = to = unprocessable_ocr) — never a silent no-op. OCR engine failure
raises (OcrError) and nothing commits — the document stays `unprocessable_ocr`
for retry, never silently dropped."""
from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy.orm import Session

from . import audit
from .config import settings
from .models import Document
from .object_store import ObjectStore
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
    store: ObjectStore,
    threshold: int | None = None,
    engine: OcrEngine | None = None,
) -> State:
    """OCR one `unprocessable_ocr` document and re-classify it.

    Fetch the scanned bytes by the document's key, OCR them into a text-layer
    PDF, then re-apply the SAME characters-per-page threshold via profile_pdf on
    that PDF. At/above: store the OCR'd PDF under its own content-addressed key,
    repoint `object_key` (the original scan object is kept), and transition to
    `extractable`. Below: the document stays `unprocessable_ocr` and the attempt
    is appended as an access-style audit record — no attempt is a silent no-op.
    """
    threshold = threshold if threshold is not None else settings.born_digital_threshold
    engine = engine or _default_ocr_engine()
    state = current_state(session, document_id)
    if state != State.UNPROCESSABLE_OCR:
        raise ValueError(f"OCR recovery only applies to unprocessable_ocr, not {state}")
    doc = session.get(Document, document_id)
    pdf_bytes = store.get(doc.object_key)
    ocr_bytes = engine.ocr(pdf_bytes)  # OcrError propagates: loud, retryable, no skip
    metric = profile_pdf(ocr_bytes, threshold)
    payload = {k: metric[k] for k in ("chars", "pages", "bytes")}
    if not metric["born_digital"]:
        # Too little text: state unchanged, but the attempt leaves a trace
        # (from = to, like `deanonymize`) so re-OCR decisions have audit data.
        audit.append(
            session,
            document_id=document_id,
            from_state=State.UNPROCESSABLE_OCR.value,
            to_state=State.UNPROCESSABLE_OCR.value,
            step="ocr",
            payload=payload,
        )
        return State.UNPROCESSABLE_OCR
    new_key = "documents/" + hashlib.sha256(ocr_bytes).hexdigest()
    store.put(new_key, ocr_bytes)  # own content-addressed object; scan is kept
    old_key = doc.object_key
    doc.object_key = new_key  # documents-table column, not an audit record
    session.flush()
    transition(
        session, document_id, State.EXTRACTABLE, step="ocr",
        payload={**payload, "old_object_key": old_key, "new_object_key": new_key},
    )
    return State.EXTRACTABLE
