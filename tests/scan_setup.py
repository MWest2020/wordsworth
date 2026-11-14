# SPDX-License-Identifier: MIT
"""Shared setup for `delete-removes-original-scan` tests: a document
recovered through `recover` (never by writing an `ocr` record by hand), so
these tests exercise the real audit trail the claim reads -- the same device
`test_ocr_sealed.py` and `test_shred_deletion.py` use."""
from __future__ import annotations

from wordsworth.audit import current_state
from wordsworth.models import Document
from wordsworth.ocr import FixedOcrEngine
from wordsworth.pipeline import ingest, process
from wordsworth.recovery import recover
from wordsworth.states import State

RECOVERY_TEXT = "Herstelde tekst van een gescand stuk, nu met een laag. " * 3


def recover_now(session, store, document_id, *, text: str = RECOVERY_TEXT,
                threshold: int = 10) -> str:
    """Run OCR recovery on ``document_id`` (processed into `unprocessable_ocr`
    first, if it is not there yet). Returns the OCR'd PDF's object key."""
    if current_state(session, document_id) != State.UNPROCESSABLE_OCR:
        assert process(session, document_id, store) == State.UNPROCESSABLE_OCR
        session.commit()
    final = recover(session, document_id, store, threshold=threshold,
                    engine=FixedOcrEngine(text))
    session.commit()
    assert final == State.EXTRACTABLE
    return session.get(Document, document_id).object_key


def recover_document(session, store, scanned_pdf, *, text: str = RECOVERY_TEXT,
                     threshold: int = 10):
    """Ingest ``scanned_pdf`` and recover it. Returns ``(document_id,
    scan_key, ocr_key)``; the document's row points at ``ocr_key`` and its
    `ocr` audit record names ``scan_key`` as `old_object_key`."""
    doc = ingest(session, store, scanned_pdf)
    session.commit()
    scan_key = doc.object_key
    ocr_key = recover_now(session, store, doc.id, text=text, threshold=threshold)
    return doc.id, scan_key, ocr_key
