# SPDX-License-Identifier: MIT
"""The OCR gap, closed (`originals-ocr-sealed`): `recovery.recover` used to
write the OCR'd PDF as a plain object (`store.put`, not `write_original`) even
when `store` is an `OriginalsStore` -- the one write `originals-ingest-switch`
did not move onto the seam (pinned here as
`test_ocr_write_is_plaintext_but_still_opens_through_read_original`, 2026-11-09
..2026-11-11). It now writes through `write_original` like any other
original: sealed, under its own key row. It still reads the scan through
`read_original`, and the sealed object it writes still opens through
`read_original` afterwards."""
from __future__ import annotations

from wordsworth.document_keys import DocumentKeys
from wordsworth.models import Document
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.ocr import FixedOcrEngine
from wordsworth.originals_envelope import HEADER_MAGIC
from wordsworth.originals_io import read_original, write_original
from wordsworth.originals_store import OriginalsStore
from wordsworth.pipeline import process, register
from wordsworth.recovery import recover
from wordsworth.states import State
from wordsworth.transit import FakeTransit


def _transit_for(name: str) -> FakeTransit:
    return FakeTransit()


def _originals_store() -> OriginalsStore:
    return OriginalsStore(InMemoryObjectStore(), DocumentKeys(_transit_for))


def test_ocr_write_is_sealed_and_opens_through_read_original(
    session_factory, scanned_pdf,
):
    store = _originals_store()
    marker = "Herstelde tekst uit een scan. " * 3
    with session_factory() as session:
        doc = register(session, "documents/sealed-ocr-gap")
        session.flush()
        scan_key = doc.object_key
        write_original(session, store, doc.id, scan_key, scanned_pdf)
        session.commit()
        assert process(session, doc.id, store) == State.UNPROCESSABLE_OCR
        session.commit()

        engine = FixedOcrEngine(marker)
        final = recover(session, doc.id, store, threshold=10, engine=engine)
        session.commit()

        new_key = session.get(Document, doc.id).object_key
        raw = store.objects.get_raw(new_key)

        assert raw is not None
        assert raw.startswith(HEADER_MAGIC)  # sealed: the gap is closed
        assert marker.encode() not in raw  # ciphertext, not the plain OCR text
        assert read_original(session, store, new_key) != raw  # opens via unwrap, not as-is

    assert final == State.EXTRACTABLE
    assert new_key != scan_key  # the scan is kept under its own key
