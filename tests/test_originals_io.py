# SPDX-License-Identifier: MIT
"""The ingest seam (`originals-ingest-seam`): `OriginalsStore` as a plain
`ObjectStore` (task 1.1), and `read_original`/`write_original`, the only way
code reads or writes an original (task 1.2)."""
import pytest

from wordsworth.document_keys import DocumentKeys
from wordsworth.object_store import InMemoryObjectStore, ObjectStore, SealedObjectError
from wordsworth.originals_io import read_original, write_original
from wordsworth.originals_store import OriginalsStore, PutResult
from wordsworth.pipeline import register
from wordsworth.transit import FakeTransit


def _transit_for(name: str) -> FakeTransit:
    return FakeTransit()


def _doc(session, key="documents/a"):
    doc = register(session, key)
    session.flush()
    return doc


def _originals_store() -> OriginalsStore:
    return OriginalsStore(InMemoryObjectStore(), DocumentKeys(_transit_for))


# --- OriginalsStore satisfies ObjectStore (task 1.1) ------------------------

def test_originals_store_satisfies_object_store_protocol():
    assert isinstance(_originals_store(), ObjectStore)


def test_originals_store_round_trips_a_plain_object():
    store = _originals_store()
    store.put("documents/plain", b"hello bytes")
    assert store.exists("documents/plain") is True
    assert store.get("documents/plain") == b"hello bytes"
    assert store.get_raw("documents/plain") == b"hello bytes"
    assert dict(store.iter_objects("documents/"))["documents/plain"] is not None
    assert store.delete("documents/plain") is True
    assert store.exists("documents/plain") is False


def test_originals_store_get_refuses_an_object_sealed_via_put_original(session):
    store = _originals_store()
    doc = _doc(session)
    store.put_original(session, doc.id, doc.object_key, b"the pdf bytes")
    session.commit()
    with pytest.raises(SealedObjectError):
        store.get(doc.object_key)


# --- read_original / write_original (task 1.2) ------------------------------

def test_write_then_read_through_a_plain_store():
    store = InMemoryObjectStore()
    first = write_original(None, store, None, "documents/a", b"hello")
    assert first is PutResult.WROTE
    second = write_original(None, store, None, "documents/a", b"hello again")
    assert second is PutResult.UNCHANGED
    assert read_original(None, store, "documents/a") == b"hello again"


def test_write_then_read_through_an_originals_store(session):
    store = _originals_store()
    doc = _doc(session)
    result = write_original(session, store, doc.id, doc.object_key, b"the pdf bytes")
    assert result is PutResult.WROTE

    sealed = store.objects.get_raw(doc.object_key)
    assert b"the pdf bytes" not in sealed  # header present, plaintext absent

    assert read_original(session, store, doc.object_key) == b"the pdf bytes"


def test_read_original_refuses_a_sealed_object_through_a_plain_store(session):
    store = _originals_store()
    doc = _doc(session)
    write_original(session, store, doc.id, doc.object_key, b"the pdf bytes")
    session.commit()
    with pytest.raises(SealedObjectError):
        read_original(session, store.objects, doc.object_key)
