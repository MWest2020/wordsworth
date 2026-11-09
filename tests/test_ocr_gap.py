# SPDX-License-Identifier: MIT
"""The OCR gap, pinned (`originals-ingest-switch` task 2.1): `recovery.recover`
writes the OCR'd PDF as a plain object (`store.put`, not `write_original`)
even when `store` is an `OriginalsStore` -- the one write this change does not
move onto the seam. It still reads the scan through `read_original`, and the
plain object it writes still opens through `read_original` afterwards
(`OriginalsStore.get_original`'s legacy-plaintext path returns an unsealed
object as-is). `originals-ocr-sealed` is the change that inverts this and
seals the OCR write too."""
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


def test_ocr_write_is_plaintext_but_still_opens_through_read_original(
    session_factory, scanned_pdf,
):
    store = _originals_store()
    with session_factory() as session:
        doc = register(session, "documents/sealed-ocr-gap")
        session.flush()
        scan_key = doc.object_key
        write_original(session, store, doc.id, scan_key, scanned_pdf)
        session.commit()
        assert process(session, doc.id, store) == State.UNPROCESSABLE_OCR
        session.commit()

        engine = FixedOcrEngine("Herstelde tekst uit een scan. " * 3)
        final = recover(session, doc.id, store, threshold=10, engine=engine)
        session.commit()

        new_key = session.get(Document, doc.id).object_key
        raw = store.objects.get_raw(new_key)

        assert raw is not None
        assert not raw.startswith(HEADER_MAGIC)  # plaintext: the write is the gap
        assert read_original(session, store, new_key) == raw  # still opens, as-is

    assert final == State.EXTRACTABLE
    assert new_key != scan_key  # the scan is kept under its own key
