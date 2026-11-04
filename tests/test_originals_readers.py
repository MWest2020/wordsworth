# SPDX-License-Identifier: MIT
"""The five readers of an original move onto `read_original`
(`originals-ingest-readers`): `pipeline.process`, `pipeline.reanonymize`, OCR
recovery's input read, and the redacted/reveal PDF routes. DB-backed: runs
against a real Postgres and skips locally without one, like the other
integration tests.

Proves tasks 1.1-1.4: a document sealed with `write_original` over an
`OriginalsStore` reaches the same outcomes as the same bytes through a plain
store, `OriginalsKeyUnavailable` from a read maps to 503 on the two PDF
routes, and no plain `.get(doc.object_key)`/`.get(document.object_key)`
remains outside `originals_io.py`."""
from __future__ import annotations

import io
import pathlib
import re

import pypdf
from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.document_keys import DocumentKeys
from wordsworth.grants import InMemoryGrantStore
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.ocr import FixedOcrEngine
from wordsworth.originals_io import write_original
from wordsworth.originals_store import OriginalsStore
from wordsworth.pipeline import ingest, process, reanonymize, register
from wordsworth.pseudonymizer import Pseudonymizer
from wordsworth.recovery import recover
from wordsworth.states import State
from wordsworth.transit import FakeTransit


def _transit_for(name: str) -> FakeTransit:
    return FakeTransit()


def _originals_store() -> OriginalsStore:
    return OriginalsStore(InMemoryObjectStore(), DocumentKeys(_transit_for))


def _sealed_doc(session, store, data: bytes, key: str):
    doc = register(session, key)
    session.flush()
    write_original(session, store, doc.id, doc.object_key, data)
    return doc


# --- task 1.1: process and reanonymize read through read_original ----------

def test_process_through_a_sealed_original_matches_a_plain_store(
    session_factory, mem_store, mem_index, fake_embedder, born_digital_pdf,
):
    with session_factory() as s:
        plain_doc = ingest(s, mem_store, born_digital_pdf)
        s.commit()
        assert process(s, plain_doc.id, mem_store, search_index=mem_index,
                       embedder=fake_embedder) == State.INDEXED
        s.commit()
        plain_text = mem_index._docs[str(plain_doc.id)][0]

    originals = _originals_store()
    with session_factory() as s:
        doc = _sealed_doc(s, originals, born_digital_pdf, "documents/sealed-process")
        s.commit()
        final = process(s, doc.id, originals, search_index=mem_index,
                        embedder=fake_embedder)
        s.commit()

    assert final == State.INDEXED
    assert mem_index._docs[str(doc.id)][0] == plain_text


def test_reanonymize_through_a_sealed_original_succeeds(
    session_factory, mem_index, fake_embedder, born_digital_pdf,
):
    originals = _originals_store()
    with session_factory() as s:
        doc = _sealed_doc(s, originals, born_digital_pdf, "documents/sealed-reanon")
        s.commit()
        assert process(s, doc.id, originals, search_index=mem_index,
                       embedder=fake_embedder) == State.INDEXED
        s.commit()
        result = reanonymize(s, doc.id, originals, search_index=mem_index,
                             embedder=fake_embedder)
        s.commit()

    assert result == State.INDEXED


# --- task 1.2: OCR recovery reads through read_original --------------------

class _RecordingOcrEngine:
    lang = "nld"

    def __init__(self, text: str):
        self._text = text
        self.received: bytes | None = None

    def ocr(self, pdf_bytes: bytes) -> bytes:
        self.received = pdf_bytes  # the plaintext scan, never ciphertext
        return FixedOcrEngine(self._text).ocr(pdf_bytes)


def test_ocr_recovery_reads_the_sealed_scan_as_plaintext(session_factory, scanned_pdf):
    originals = _originals_store()
    with session_factory() as s:
        doc = _sealed_doc(s, originals, scanned_pdf, "documents/sealed-scan")
        s.commit()
        assert process(s, doc.id, originals) == State.UNPROCESSABLE_OCR
        s.commit()

        engine = _RecordingOcrEngine("Herstelde tekst uit een scan. " * 3)
        final = recover(s, doc.id, originals, threshold=10, engine=engine)
        s.commit()

    assert final == State.EXTRACTABLE
    assert engine.received == scanned_pdf


# --- task 1.3: the two PDF routes read through read_original ---------------

def _prepare_sealed_with_box_map(session_factory, originals, mem_index, fake_embedder,
                                 pdf, key):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = _sealed_doc(s, originals, pdf, key)
        s.commit()
        process(s, doc.id, originals,
               anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
               search_index=mem_index, embedder=fake_embedder,
               key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()
        return kp, doc.id


def test_redacted_pdf_served_from_a_sealed_original(
    session_factory, mem_index, fake_embedder, born_digital_pii_pdf,
):
    originals = _originals_store()
    kp, doc_id = _prepare_sealed_with_box_map(
        session_factory, originals, mem_index, fake_embedder,
        born_digital_pii_pdf, "documents/sealed-redacted")

    client = TestClient(create_app(session_factory=session_factory, store=originals,
                                   key_provider=kp))
    r = client.get(f"/documents/{doc_id}/redacted.pdf")

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    pypdf.PdfReader(io.BytesIO(r.content))  # a valid PDF


def test_reveal_pdf_served_from_a_sealed_original(
    session_factory, mem_index, fake_embedder, born_digital_pii_pdf,
):
    originals = _originals_store()
    kp, doc_id = _prepare_sealed_with_box_map(
        session_factory, originals, mem_index, fake_embedder,
        born_digital_pii_pdf, "documents/sealed-reveal")
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)

    client = TestClient(create_app(session_factory=session_factory, store=originals,
                                   key_provider=kp, grant_store=gs))
    r = client.post(f"/documents/{doc_id}/reveal.pdf",
                    json={"grant_id": grant.grant_id})

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    pypdf.PdfReader(io.BytesIO(r.content))  # a valid PDF


class _RefusingTransit:
    def wrap(self, plaintext: bytes) -> bytes:
        raise RuntimeError("key service down")

    def unwrap(self, ciphertext: bytes) -> bytes:
        raise RuntimeError("key service down")


def test_redacted_pdf_maps_key_unavailable_to_503(
    session_factory, mem_index, fake_embedder, born_digital_pii_pdf,
):
    objects = InMemoryObjectStore()
    working = OriginalsStore(objects, DocumentKeys(_transit_for))
    kp, doc_id = _prepare_sealed_with_box_map(
        session_factory, working, mem_index, fake_embedder,
        born_digital_pii_pdf, "documents/sealed-key-unavailable")

    # A fresh DocumentKeys (empty unwrap cache) over the same objects, bound to
    # a transit that always refuses -- the key service is down for this read.
    refusing = OriginalsStore(objects, DocumentKeys(lambda name: _RefusingTransit()))
    client = TestClient(create_app(session_factory=session_factory, store=refusing,
                                   key_provider=kp))
    r = client.get(f"/documents/{doc_id}/redacted.pdf")

    assert r.status_code == 503
    assert r.json()["detail"] == "key service unavailable"


def test_reveal_pdf_maps_key_unavailable_to_503(
    session_factory, mem_index, fake_embedder, born_digital_pii_pdf,
):
    objects = InMemoryObjectStore()
    working = OriginalsStore(objects, DocumentKeys(_transit_for))
    kp, doc_id = _prepare_sealed_with_box_map(
        session_factory, working, mem_index, fake_embedder,
        born_digital_pii_pdf, "documents/sealed-reveal-key-unavailable")
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)

    refusing = OriginalsStore(objects, DocumentKeys(lambda name: _RefusingTransit()))
    client = TestClient(create_app(session_factory=session_factory, store=refusing,
                                   key_provider=kp, grant_store=gs))
    r = client.post(f"/documents/{doc_id}/reveal.pdf",
                    json={"grant_id": grant.grant_id})

    assert r.status_code == 503
    assert r.json()["detail"] == "key service unavailable"


# --- task 1.4: no plain read of an original remains -------------------------

def test_no_plain_read_of_an_original_remains():
    # `store.get(doc.object_key)` / `store.get(document.object_key)`: a plain
    # read of an original, bypassing the seam. Scoped to `store.get(...)` so
    # it does not flag unrelated lookups like `names.get(doc.object_key)`
    # (backfill_filenames.py), which read a dict, not an object store.
    pattern = re.compile(r"store\.get\(doc\.object_key\)|store\.get\(document\.object_key\)")
    src = pathlib.Path(__file__).resolve().parent.parent / "src" / "wordsworth"
    offenders = [
        str(path) for path in src.rglob("*.py")
        if path.name != "originals_io.py" and pattern.search(path.read_text())
    ]
    assert offenders == []
