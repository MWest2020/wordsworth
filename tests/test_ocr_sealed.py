# SPDX-License-Identifier: MIT
"""`originals-ocr-sealed`: OCR recovery checks who owns the OCR'd PDF's key
*before* writing anything, and writes it sealed through the originals seam
(`recovery.py:78-79`, named on #306) -- closing the gap `test_ocr_gap.py`
pinned after `originals-ingest-switch`."""
from __future__ import annotations

import base64
import hashlib
import logging

import pytest
from sqlalchemy import func, select

from wordsworth import document_keys, recovery
from wordsworth.document_keys import DocumentKeyRecord, DocumentKeys, OriginalsKeyUnavailable
from wordsworth.models import Document
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.ocr import FixedOcrEngine, OcrError
from wordsworth.originals_envelope import HEADER_MAGIC
from wordsworth.originals_io import read_original, write_original
from wordsworth.originals_store import OriginalsStore
from wordsworth.pipeline import current_state, ingest, process, register
from wordsworth.recovery import recover
from wordsworth.states import State
from wordsworth.transit import FakeTransit

_FAKE_TRANSIT = FakeTransit()


def _transit_for(name: str) -> FakeTransit:
    return _FAKE_TRANSIT


def _originals_store(objects: InMemoryObjectStore | None = None) -> OriginalsStore:
    return OriginalsStore(objects or InMemoryObjectStore(), DocumentKeys(_transit_for))


class _RecordingEngine:
    """Captures the OCR bytes it hands back, so a test can compute the exact
    new key without calling a non-byte-deterministic engine twice (reportlab
    embeds a timestamp, so two calls with the same text are not equal)."""

    lang = "nld"

    def __init__(self, text: str):
        self._inner = FixedOcrEngine(text)
        self.ocr_bytes: bytes | None = None

    def ocr(self, pdf_bytes: bytes) -> bytes:
        self.ocr_bytes = self._inner.ocr(pdf_bytes)
        return self.ocr_bytes


# --- 1.1: the owner is checked before anything is written -------------------

#: Precomputed once -- two independent recoveries only collide on the same
#: object if the engine hands back these exact bytes (the same trick
#: `test_one_live_document.py` uses).
_OWNED_TEXT = "Deze tekst behoort al aan een ander levend document. " * 3
_OWNED_PDF = FixedOcrEngine(_OWNED_TEXT).ocr(b"%PDF-1.4")
_OWNED_KEY = "documents/" + hashlib.sha256(_OWNED_PDF).hexdigest()


class _SameOcr:
    lang = "nld"

    def ocr(self, pdf_bytes: bytes) -> bytes:
        return _OWNED_PDF


def test_owner_checked_before_write_leaves_owners_object_and_rows_untouched(
    session_factory, scanned_pdf,
):
    store = _originals_store()
    with session_factory() as s:
        owner = register(s, _OWNED_KEY)
        s.flush()
        write_original(s, store, owner.id, _OWNED_KEY, _OWNED_PDF)
        s.commit()
        owner_raw_before = store.objects.get_raw(_OWNED_KEY)

        scan = ingest(s, store, scanned_pdf)
        s.commit()
        assert process(s, scan.id, store) == State.UNPROCESSABLE_OCR
        s.commit()
        rows_before = s.execute(
            select(func.count()).select_from(DocumentKeyRecord)).scalar_one()

        result = recover(s, scan.id, store, threshold=10, engine=_SameOcr())
        s.commit()

        assert result == State.SUPERSEDED
        # Byte-for-byte unchanged: nothing was written over the owner's object.
        assert store.objects.get_raw(_OWNED_KEY) == owner_raw_before
        rows_after = s.execute(
            select(func.count()).select_from(DocumentKeyRecord)).scalar_one()
        assert rows_after == rows_before  # no key row added
        retired = s.get(Document, scan.id)
        assert retired.superseded_by == owner.id


# --- 1.2: the OCR'd PDF is written sealed, under the recovered document ----

def test_ocr_pdf_is_written_sealed_under_the_recovered_document(
    session_factory, scanned_pdf,
):
    store = _originals_store()
    text = "Tekst die nooit in de ruwe sealed bytes mag voorkomen. " * 3
    with session_factory() as s:
        doc = ingest(s, store, scanned_pdf)
        s.commit()
        scan_key = doc.object_key
        assert process(s, doc.id, store) == State.UNPROCESSABLE_OCR
        s.commit()
        scan_raw_before = store.objects.get_raw(scan_key)
        scan_row_before = s.get(DocumentKeyRecord, scan_key)
        assert scan_row_before is not None  # ingest already seals the scan
        scan_key_id_before = scan_row_before.key_id

        engine = _RecordingEngine(text)
        final = recover(s, doc.id, store, threshold=10, engine=engine)
        s.commit()

        new_key = s.get(Document, doc.id).object_key
        raw = store.objects.get_raw(new_key)
        assert raw.startswith(HEADER_MAGIC)
        assert text.encode() not in raw  # no marker string from the OCR text
        assert read_original(s, store, new_key) == engine.ocr_bytes

        row = s.get(DocumentKeyRecord, new_key)
        assert row is not None and row.document_id == doc.id

        # The scan object and its row are unchanged.
        assert store.objects.get_raw(scan_key) == scan_raw_before
        scan_row_after = s.get(DocumentKeyRecord, scan_key)
        assert scan_row_after.key_id == scan_key_id_before
        assert scan_row_after.document_id == doc.id

    assert final == State.EXTRACTABLE
    assert new_key != scan_key


def test_sealed_ocr_recovery_still_flows_through_extract_and_index(
    session_factory, scanned_pdf, mem_index, fake_embedder,
):
    """The existing extract-then-index proof (`test_ocr.py`) holds on a sealed
    object too: a recovered document's OCR text is readable and indexed, not
    just the fact that the write happened."""
    store = _originals_store()
    text = "Herstelde tekst uit een scan, nu via de sealed store. " * 3
    with session_factory() as s:
        doc = ingest(s, store, scanned_pdf)
        s.commit()
        assert process(s, doc.id, store) == State.UNPROCESSABLE_OCR
        s.commit()

        final = recover(s, doc.id, store, threshold=10, engine=FixedOcrEngine(text))
        s.commit()
        assert final == State.EXTRACTABLE

        assert process(s, doc.id, store, search_index=mem_index,
                       embedder=fake_embedder) == State.INDEXED
        s.commit()
        doc_id = doc.id

    hits = mem_index.search("Herstelde tekst")
    assert [h.document_id for h in hits] == [str(doc_id)]


# --- 1.3: a failure after the write deletes it; a retry recovers -----------

def test_failure_after_the_write_deletes_the_object_and_a_retry_recovers(
    session_factory, scanned_pdf, monkeypatch,
):
    store = _originals_store()
    text = "Tekst die bij een fout na de write verwijderd moet worden. " * 3
    with session_factory() as s:
        doc = ingest(s, store, scanned_pdf)
        s.commit()
        scan_key = doc.object_key
        assert process(s, doc.id, store) == State.UNPROCESSABLE_OCR
        s.commit()

        engine = _RecordingEngine(text)

        def _boom(*args, **kwargs):
            raise RuntimeError("transition boom")

        monkeypatch.setattr(recovery, "transition", _boom)
        with pytest.raises(RuntimeError, match="transition boom"):
            recover(s, doc.id, store, threshold=10, engine=engine)
        s.rollback()

        new_key = "documents/" + hashlib.sha256(engine.ocr_bytes).hexdigest()
        assert not store.exists(new_key)  # deleted, not left dangling
        assert current_state(s, doc.id) == State.UNPROCESSABLE_OCR
        assert s.get(Document, doc.id).object_key == scan_key

        monkeypatch.undo()
        retry_engine = _RecordingEngine(text)
        final = recover(s, doc.id, store, threshold=10, engine=retry_engine)
        s.commit()

        assert final == State.EXTRACTABLE
        retried_key = s.get(Document, doc.id).object_key
        assert read_original(s, store, retried_key) == retry_engine.ocr_bytes


# --- 1.4: fail closed when the Transit refuses ------------------------------

class _WrapRefusingTransit:
    """Unwraps normally (so reading the already-sealed scan still works) but
    refuses to wrap a fresh data key -- isolating the failure at the write."""

    def __init__(self, real: FakeTransit):
        self._real = real

    def wrap(self, plaintext: bytes) -> bytes:
        raise RuntimeError("key service down")

    def unwrap(self, ciphertext: bytes) -> bytes:
        return self._real.unwrap(ciphertext)


def test_transit_failure_at_the_write_is_fail_closed(session_factory, scanned_pdf):
    objects = InMemoryObjectStore()
    working = _originals_store(objects)
    with session_factory() as s:
        doc = ingest(s, working, scanned_pdf)
        s.commit()
        scan_key = doc.object_key
        assert process(s, doc.id, working) == State.UNPROCESSABLE_OCR
        s.commit()

        refusing = OriginalsStore(
            objects, DocumentKeys(lambda name: _WrapRefusingTransit(_FAKE_TRANSIT)))
        engine = _RecordingEngine(
            "Tekst die nooit als nieuw sealed object geschreven mag worden. " * 3)

        with pytest.raises(OriginalsKeyUnavailable):
            recover(s, doc.id, refusing, threshold=10, engine=engine)
        s.rollback()

        new_key = "documents/" + hashlib.sha256(engine.ocr_bytes).hexdigest()
        assert not objects.exists(new_key)  # nothing written
        assert current_state(s, doc.id) == State.UNPROCESSABLE_OCR
        assert s.get(Document, doc.id).object_key == scan_key


# --- 1.5: a legacy OCR'd object from before this change is left as it is ---

def test_legacy_ocr_object_recovered_again_is_left_as_is(session_factory, scanned_pdf):
    store = _originals_store()
    text = "Legacy OCR tekst van voor deze wijziging, ongewijzigd gelaten. " * 3
    legacy_bytes = FixedOcrEngine(text).ocr(b"%PDF-1.4")
    legacy_key = "documents/" + hashlib.sha256(legacy_bytes).hexdigest()

    class _SameBytes:
        lang = "nld"

        def ocr(self, pdf_bytes: bytes) -> bytes:
            return legacy_bytes

    with session_factory() as s:
        doc = ingest(s, store, scanned_pdf)
        s.commit()
        assert process(s, doc.id, store) == State.UNPROCESSABLE_OCR
        s.commit()
        # A plain write from before this change: no key row, no seal.
        store.objects.put(legacy_key, legacy_bytes)

        final = recover(s, doc.id, store, threshold=10, engine=_SameBytes())
        s.commit()

        assert final == State.EXTRACTABLE
        assert s.get(Document, doc.id).object_key == legacy_key
        assert store.objects.get_raw(legacy_key) == legacy_bytes  # left as it is
        assert s.get(DocumentKeyRecord, legacy_key) is None  # still no key row
        assert read_original(s, store, legacy_key) == legacy_bytes  # the document reads it


# --- 1.6: no plaintext or key bytes reach the logs --------------------------

def test_no_plaintext_or_key_bytes_in_logs_during_recovery_and_its_failures(
    session_factory, scanned_pdf, monkeypatch, caplog,
):
    fixed_material = bytes(range(32))
    monkeypatch.setattr(
        document_keys, "_mint_dek",
        lambda: document_keys.DataKey("deadbeefcafe", fixed_material))

    marker = ("Dit markerzinnetje mag nooit letterlijk, als hex of als base64 "
              "in een logregel staan.")
    needles = [
        marker, marker.encode().hex(), base64.b64encode(marker.encode()).decode(),
        fixed_material.hex(), base64.b64encode(fixed_material).decode(),
    ]

    store = _originals_store()
    with caplog.at_level(logging.DEBUG):
        with session_factory() as s:
            doc = ingest(s, store, scanned_pdf)
            s.commit()
            assert process(s, doc.id, store) == State.UNPROCESSABLE_OCR
            s.commit()

            class _Boom:
                lang = "nld"

                def ocr(self, pdf_bytes: bytes) -> bytes:
                    raise OcrError("tesseract crashed")

            with pytest.raises(OcrError):
                recover(s, doc.id, store, engine=_Boom())
            s.rollback()

            # Sub-threshold: from = to, no recovery, still audited.
            assert recover(s, doc.id, store, threshold=10_000,
                          engine=FixedOcrEngine(marker)) == State.UNPROCESSABLE_OCR
            s.commit()

            # A successful, sealed recovery.
            assert recover(s, doc.id, store, threshold=10,
                          engine=FixedOcrEngine(marker)) == State.EXTRACTABLE
            s.commit()

    for record in caplog.records:
        line = record.getMessage()
        for needle in needles:
            assert needle not in line
