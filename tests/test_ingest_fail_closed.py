# SPDX-License-Identifier: MIT
"""`originals-ingest-write`: ingest fails closed when the key service refuses
-- both pseudonymisation modes, a batch stops at the first refusal, and a
refusal from `process`'s read-back leaves the already-written object alone.
Tasks 2.1, 2.2 and 2.4 (2.3 is the existing batch tests, unchanged)."""
from __future__ import annotations

import hashlib
import io

from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.api import create_app
from wordsworth.document_keys import DocumentKeys
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.originals_store import OriginalsStore
from wordsworth.pseudonymizer import Pseudonymizer


def _pdf(text: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 800, text)
    c.showPage()
    c.save()
    return buf.getvalue()


def _key_for(data: bytes) -> str:
    return "documents/" + hashlib.sha256(data).hexdigest()


class _AlwaysRefusingTransit:
    def wrap(self, plaintext: bytes) -> bytes:
        raise RuntimeError("key service down")

    def unwrap(self, ciphertext: bytes) -> bytes:
        raise RuntimeError("key service down")


def _refusing_store() -> OriginalsStore:
    return OriginalsStore(InMemoryObjectStore(),
                          DocumentKeys(lambda name: _AlwaysRefusingTransit()))


# --- task 2.1: fail closed at the API, both pseudonymisation modes ---------

def test_irreversible_mode_fails_closed_on_key_refusal(
    session_factory, mem_index, fake_embedder,
):
    store = _refusing_store()
    pdf_bytes = _pdf("Onbereikbare sleuteldienst, irreversibel. " * 3)
    client = TestClient(create_app(
        session_factory=session_factory, store=store, search_index=mem_index,
        embedder=fake_embedder, anonymizer=DeterministicAnonymizer()))

    r = client.post("/ingest", params={"dossier": "zaak"},
                    files=[("files", ("a.pdf", pdf_bytes, "application/pdf"))])

    assert r.status_code == 503
    assert r.json()["detail"] == "key service unavailable"
    assert not store.objects.exists(_key_for(pdf_bytes))


def test_reversible_mode_fails_closed_on_key_refusal(
    session_factory, mem_index, fake_embedder,
):
    store = _refusing_store()
    kp = InMemoryKeyProvider()
    pdf_bytes = _pdf("Onbereikbare sleuteldienst, reversibel. " * 3)
    client = TestClient(create_app(
        session_factory=session_factory, store=store, search_index=mem_index,
        embedder=fake_embedder, key_provider=kp,
        anonymizer_factory=lambda s: Pseudonymizer(kp, PostgresMappingStore(s))))

    r = client.post("/ingest", params={"dossier": "zaak"},
                    files=[("files", ("a.pdf", pdf_bytes, "application/pdf"))])

    assert r.status_code == 503
    assert r.json()["detail"] == "key service unavailable"
    assert not store.objects.exists(_key_for(pdf_bytes))


# --- task 2.2: the batch stops at the first unavailable key ----------------

def _refusing_from(n: int):
    """A transit factory sharing one counter and one working inner transit:
    `wrap` (used by `mint`, once per new object) refuses from the n-th call
    on; `unwrap` always succeeds, so a file minted before the refusal still
    reads back fine."""
    from wordsworth.transit import FakeTransit

    inner = FakeTransit()
    calls = [0]

    class _Transit:
        def wrap(self, plaintext: bytes) -> bytes:
            calls[0] += 1
            if calls[0] >= n:
                raise RuntimeError("key service down")
            return inner.wrap(plaintext)

        def unwrap(self, ciphertext: bytes) -> bytes:
            return inner.unwrap(ciphertext)

    return lambda name: _Transit()


def test_batch_stops_at_the_first_unavailable_key(
    session_factory, mem_index, fake_embedder,
):
    store = OriginalsStore(InMemoryObjectStore(), DocumentKeys(_refusing_from(2)))
    pdfs = [_pdf(f"Document nummer {i} in de batch. " * 3) for i in range(1, 4)]
    client = TestClient(create_app(
        session_factory=session_factory, store=store, search_index=mem_index,
        embedder=fake_embedder, anonymizer=DeterministicAnonymizer()))

    r = client.post(
        "/ingest", params={"dossier": "zaak"},
        files=[("files", (f"{i}.pdf", data, "application/pdf"))
              for i, data in enumerate(pdfs, start=1)])

    assert r.status_code == 503
    body = r.json()
    assert body["detail"] == "key service unavailable"
    assert body["total"] == 3
    assert len(body["results"]) == 1
    assert body["results"][0]["filename"] == "1.pdf"
    assert body["results"][0]["state"] == "indexed"
    assert body["indexed"] == 1

    assert store.objects.exists(_key_for(pdfs[0]))
    assert not store.objects.exists(_key_for(pdfs[1]))
    assert not store.objects.exists(_key_for(pdfs[2]))


# --- task 2.4: a read-back refusal leaves the written object -----------

class _WriteOkReadFailsTransit:
    def wrap(self, plaintext: bytes) -> bytes:
        return plaintext

    def unwrap(self, ciphertext: bytes) -> bytes:
        raise RuntimeError("key service down")


def test_read_back_refusal_leaves_the_sealed_object(
    session_factory, mem_index, fake_embedder,
):
    # cache_ttl=0 forces every unwrap past the (empty) cache and into the
    # transit, so a write through this very key succeeding does not also make
    # its read-back succeed from the unwrap cache.
    store = OriginalsStore(
        InMemoryObjectStore(),
        DocumentKeys(lambda name: _WriteOkReadFailsTransit(), cache_ttl=0))
    pdf_bytes = _pdf("Schrijven lukt, teruglezen niet. " * 3)
    client = TestClient(create_app(
        session_factory=session_factory, store=store, search_index=mem_index,
        embedder=fake_embedder, anonymizer=DeterministicAnonymizer()))

    r = client.post("/ingest", params={"dossier": "zaak"},
                    files=[("files", ("a.pdf", pdf_bytes, "application/pdf"))])

    assert r.status_code == 503
    assert r.json()["detail"] == "key service unavailable"
    # no delete on the process path: the write that already committed stays.
    assert store.objects.exists(_key_for(pdf_bytes))
