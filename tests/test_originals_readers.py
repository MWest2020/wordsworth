# SPDX-License-Identifier: MIT
"""`originals-ingest-readers`: the five readers of an original move onto
`read_original` (task 1.1-1.3), and no plain read of an original remains
outside `originals_io.py` (task 1.4). DB-backed: runs against a real Postgres
and skips locally without one, like the other DB integration tests."""
from __future__ import annotations

import io
from pathlib import Path

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
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State
from wordsworth.transit import FakeTransit


def _transit_for(name: str) -> FakeTransit:
    return FakeTransit()


def _originals_store(objects: InMemoryObjectStore | None = None) -> OriginalsStore:
    return OriginalsStore(objects or InMemoryObjectStore(), DocumentKeys(_transit_for))


def _registered_and_sealed(session, originals_store, pdf_bytes, object_key):
    doc = register(session, object_key)
    session.flush()
    write_original(session, originals_store, doc.id, doc.object_key, pdf_bytes)
    return doc


# --- task 1.1: pipeline.process / pipeline.reanonymize ----------------------

def test_process_through_an_originals_store_matches_a_plain_store(
    session_factory, mem_store, fake_embedder, born_digital_pdf,
):
    plain_index = InMemoryIndex()
    with session_factory() as s:
        plain_doc = ingest(s, mem_store, born_digital_pdf)
        s.commit()
        assert process(s, plain_doc.id, mem_store, search_index=plain_index,
                       embedder=fake_embedder) is State.INDEXED
        s.commit()
        plain_text, _plain_key, _plain_vec = plain_index._docs[str(plain_doc.id)]

    originals_store = _originals_store()
    sealed_index = InMemoryIndex()
    with session_factory() as s:
        doc = _registered_and_sealed(s, originals_store, born_digital_pdf,
                                     "documents/sealed-process")
        s.commit()
        final = process(s, doc.id, originals_store, search_index=sealed_index,
                        embedder=fake_embedder)
        s.commit()
        assert final is State.INDEXED
        sealed_text, _sealed_key, _sealed_vec = sealed_index._docs[str(doc.id)]

    assert sealed_text == plain_text


def test_reanonymize_through_an_originals_store_succeeds(
    session_factory, fake_embedder, born_digital_pdf,
):
    originals_store = _originals_store()
    index = InMemoryIndex()
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = _registered_and_sealed(s, originals_store, born_digital_pdf,
                                     "documents/sealed-reanonymize")
        s.commit()
        process(s, doc.id, originals_store,
               anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
               search_index=index, embedder=fake_embedder,
               key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()

        result = reanonymize(s, doc.id, originals_store,
                             anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                             search_index=index, embedder=fake_embedder,
                             key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()
    assert result is State.INDEXED


# --- task 1.2: OCR recovery --------------------------------------------------

def test_ocr_recovery_reads_a_sealed_scan_through_read_original(
    session_factory, scanned_pdf,
):
    originals_store = _originals_store()
    received: dict[str, bytes] = {}

    class RecordingOcrEngine:
        lang = "nld"

        def ocr(self, pdf_bytes: bytes) -> bytes:
            received["bytes"] = pdf_bytes
            return FixedOcrEngine("Herstelde tekst uit een scan. " * 3).ocr(pdf_bytes)

    with session_factory() as s:
        doc = _registered_and_sealed(s, originals_store, scanned_pdf,
                                     "documents/sealed-scan")
        s.commit()
        assert process(s, doc.id, originals_store) is State.UNPROCESSABLE_OCR
        s.commit()

        final = recover(s, doc.id, originals_store, threshold=10,
                        engine=RecordingOcrEngine())
        s.commit()

    assert final is State.EXTRACTABLE
    assert received["bytes"] == scanned_pdf  # the engine got plaintext, not a sealed envelope


# --- task 1.3: the two PDF routes --------------------------------------------

def _prepare_served_document(session_factory, originals_store, index, embedder, pdf,
                             kp, object_key):
    with session_factory() as s:
        doc = _registered_and_sealed(s, originals_store, pdf, object_key)
        s.commit()
        process(s, doc.id, originals_store,
               anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
               search_index=index, embedder=embedder,
               key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()
        return doc.id


def test_redacted_and_reveal_pdf_served_through_an_originals_store(
    session_factory, fake_embedder, born_digital_pii_pdf,
):
    originals_store = _originals_store()
    kp = InMemoryKeyProvider()
    doc_id = _prepare_served_document(session_factory, originals_store, InMemoryIndex(),
                                      fake_embedder, born_digital_pii_pdf, kp,
                                      "documents/sealed-served")
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    client = TestClient(create_app(session_factory=session_factory, store=originals_store,
                                   key_provider=kp, grant_store=gs))

    r1 = client.get(f"/documents/{doc_id}/redacted.pdf")
    assert r1.status_code == 200
    assert r1.headers["content-type"] == "application/pdf"
    pypdf.PdfReader(io.BytesIO(r1.content))  # parses as a PDF

    r2 = client.post(f"/documents/{doc_id}/reveal.pdf",
                     json={"grant_id": grant.grant_id})
    assert r2.status_code == 200
    assert r2.headers["content-type"] == "application/pdf"
    pypdf.PdfReader(io.BytesIO(r2.content))


def test_redacted_pdf_maps_key_unavailable_to_503(
    session_factory, fake_embedder, born_digital_pii_pdf,
):
    objects = InMemoryObjectStore()
    originals_store = _originals_store(objects)
    kp = InMemoryKeyProvider()
    doc_id = _prepare_served_document(session_factory, originals_store, InMemoryIndex(),
                                      fake_embedder, born_digital_pii_pdf, kp,
                                      "documents/sealed-key-unavailable")

    class BoomTransit:
        def wrap(self, plaintext: bytes) -> bytes:
            raise RuntimeError("key service down")

        def unwrap(self, ciphertext: bytes) -> bytes:
            raise RuntimeError("key service down")

    refusing_store = OriginalsStore(objects, DocumentKeys(lambda name: BoomTransit()))
    client = TestClient(create_app(session_factory=session_factory, store=refusing_store,
                                   key_provider=kp))
    r = client.get(f"/documents/{doc_id}/redacted.pdf")
    assert r.status_code == 503
    assert r.json()["detail"] == "key service unavailable"


# --- task 1.4: no plain read of an original remains -------------------------

def test_no_plain_read_of_an_original_remains_outside_originals_io():
    src = Path(__file__).resolve().parent.parent / "src" / "wordsworth"
    offenders = []
    for path in src.rglob("*.py"):
        if path.name == "originals_io.py":
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if "store.get(doc.object_key)" in line or "store.get(document.object_key)" in line:
                offenders.append(f"{path.relative_to(src)}:{lineno}: {line.strip()}")
    assert offenders == []
