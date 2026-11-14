# SPDX-License-Identifier: MIT
"""#452 review: an ingest of a scan's bytes racing OCR recovery retiring that
scan (`supersede(..., as_object=...)`).

`supersede` used to append its audit records (the chain's advisory lock) and
only then update `superseded_by` (the row lock), the reverse of an ingest,
which holds the row FOR SHARE and appends after: `DeadlockDetected`. Now
`supersede` locks the copy's row before anything else."""
from __future__ import annotations

import hashlib
import threading

from sqlalchemy import select

from race_setup import SpyOriginalsStore, run, wait_for_a_lock_waiter
from wordsworth.audit import verify_chain
from wordsworth.models import Document, DossierDocument
from wordsworth.ocr import FixedOcrEngine
from wordsworth.originals_io import write_original
from wordsworth.pipeline import current_state, ingest, live_document_for, process, register
from wordsworth.recovery import recover
from wordsworth.states import State

_OWNED_PDF = FixedOcrEngine("Deze tekst is al van een ander document. " * 3).ocr(b"%PDF-1.4")
_OWNED_KEY = "documents/" + hashlib.sha256(_OWNED_PDF).hexdigest()


class _SameOcr:
    lang = "nld"

    def ocr(self, pdf_bytes: bytes) -> bytes:
        return _OWNED_PDF


def _scan_and_owner(session_factory, store, scanned_pdf):
    with session_factory() as s:
        owner = register(s, _OWNED_KEY)
        s.flush()
        write_original(s, store, owner.id, _OWNED_KEY, _OWNED_PDF)
        scan = ingest(s, store, scanned_pdf)
        s.commit()
        assert process(s, scan.id, store) == State.UNPROCESSABLE_OCR
        s.commit()
        return scan.id, owner.id


def _members(s):
    return set(s.execute(select(DossierDocument.document_id)).scalars().all())


def test_ingest_waits_for_a_supersede_and_lands_on_a_new_document(
        session_factory, scanned_pdf):
    store = SpyOriginalsStore()
    scan_id, owner_id = _scan_and_owner(session_factory, store, scanned_pdf)
    scan_key = "documents/" + hashlib.sha256(scanned_pdf).hexdigest()
    errors, result = {}, {}

    def ingest_scan_again():
        with session_factory() as s:
            result["id"] = ingest(s, store, scanned_pdf, dossier="zaak").id
            s.commit()

    with session_factory() as recovering:
        assert recover(recovering, scan_id, store, threshold=10,
                       engine=_SameOcr()) == State.SUPERSEDED
        worker = run(errors, "ingest", ingest_scan_again)
        wait_for_a_lock_waiter(session_factory)
        recovering.commit()
    worker.join(30)

    assert not errors, errors
    with session_factory() as s:
        assert s.get(Document, scan_id).superseded_by == owner_id
        assert result["id"] not in (scan_id, owner_id)
        assert live_document_for(s, scan_key).id == result["id"]
        assert _members(s) == {result["id"]}  # not the retired copy
        assert verify_chain(s) == (True, None)


def test_supersede_waits_for_an_ingest_holding_the_scan_and_nothing_deadlocks(
        session_factory, scanned_pdf):
    """The interleaving that deadlocked: the ingest holds the scan's row and
    has yet to append its membership record when recovery retires the scan."""
    store = SpyOriginalsStore()
    scan_id, owner_id = _scan_and_owner(session_factory, store, scanned_pdf)
    errors, locked, resume = {}, threading.Event(), threading.Event()

    def hold():
        locked.set()  # past `lock_live`: the scan's row is held FOR SHARE
        assert resume.wait(30), "never resumed"

    def ingest_scan_again():
        with session_factory() as s:
            ingest(s, store, scanned_pdf, dossier="zaak")
            s.commit()

    def recover_scan():
        with session_factory() as s:
            assert recover(s, scan_id, store, threshold=10,
                           engine=_SameOcr()) == State.SUPERSEDED
            s.commit()

    store.on_put = hold
    ingesting = run(errors, "ingest", ingest_scan_again)
    assert locked.wait(10)
    store.on_put = None
    recovering = run(errors, "recover", recover_scan)
    try:
        wait_for_a_lock_waiter(session_factory)  # recovery waits on the row
    finally:
        resume.set()
        ingesting.join(30)
        recovering.join(30)

    assert not errors, errors
    with session_factory() as s:
        assert current_state(s, scan_id) == State.SUPERSEDED
        # The membership the ingest added passed to the survivor with the rest.
        assert _members(s) == {owner_id}
        assert verify_chain(s) == (True, None)
