# SPDX-License-Identifier: MIT
"""`OriginalsStore` as an `ObjectStore` (task 1.1) and the `originals_io` seam
(task 1.2): `read_original`/`write_original` pick the sealed path for an
`OriginalsStore` and the plain path for everything else."""
import pytest

from wordsworth.document_keys import DocumentKeys
from wordsworth.object_store import InMemoryObjectStore, SealedObjectError
from wordsworth.originals_envelope import HEADER_MAGIC
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


def _originals_store():
    return OriginalsStore(InMemoryObjectStore(), DocumentKeys(_transit_for))


# --- 1.1: OriginalsStore satisfies ObjectStore ------------------------------

def test_originals_store_round_trips_a_plain_object_through_object_store_methods():
    store = _originals_store()
    assert store.exists("documents/a") is False

    store.put("documents/a", b"plain bytes")

    assert store.exists("documents/a") is True
    assert store.get("documents/a") == b"plain bytes"
    assert store.get_raw("documents/a") == b"plain bytes"
    assert list(store.iter_objects("documents/"))[0][0] == "documents/a"

    assert store.delete("documents/a") is True
    assert store.exists("documents/a") is False


def test_originals_store_get_refuses_a_sealed_object(session):
    store = _originals_store()
    doc = _doc(session)
    assert store.put_original(session, doc.id, doc.object_key, b"the pdf bytes") is PutResult.WROTE
    session.commit()

    with pytest.raises(SealedObjectError):
        store.get(doc.object_key)


# --- 1.2: read_original / write_original ------------------------------------

def test_write_then_read_through_a_plain_store_round_trips_and_reports_wrote_then_unchanged(session):
    plain = InMemoryObjectStore()
    doc = _doc(session)

    assert write_original(session, plain, doc.id, doc.object_key, b"bytes") is PutResult.WROTE
    assert read_original(session, plain, doc.object_key) == b"bytes"
    assert write_original(session, plain, doc.id, doc.object_key, b"bytes") is PutResult.UNCHANGED


def test_write_then_read_through_an_originals_store_seals_and_opens(session):
    store = _originals_store()
    doc = _doc(session)

    assert write_original(session, store, doc.id, doc.object_key, b"the pdf bytes") is PutResult.WROTE

    sealed = store.objects.get_raw(doc.object_key)
    assert sealed.startswith(HEADER_MAGIC)
    assert b"the pdf bytes" not in sealed

    assert read_original(session, store, doc.object_key) == b"the pdf bytes"


def test_read_original_through_a_plain_store_of_a_sealed_object_raises(session):
    store = _originals_store()
    doc = _doc(session)
    assert write_original(session, store, doc.id, doc.object_key, b"the pdf bytes") is PutResult.WROTE
    session.commit()

    with pytest.raises(SealedObjectError):
        read_original(session, store.objects, doc.object_key)
