# SPDX-License-Identifier: MIT
"""`OriginalsStore.put_original`'s five idempotency rules (design.md §3a),
`PutResult`'s lack of truthiness, the crash/caller-contract analysis (task
3.2), and the downgrade guard on `get_original` (task 3.4)."""
import os
import threading
import time

import pytest
from sqlalchemy import select

from wordsworth.document_keys import DocumentKeyRecord, DocumentKeys, OriginalsKeyUnavailable
from wordsworth.object_store import InMemoryObjectStore, ObjectStoreError, SealedObjectError
from wordsworth.originals_envelope import seal
from wordsworth.originals_store import OriginalsStore, PutResult
from wordsworth.pipeline import register
from wordsworth.transit import FakeTransit


def _transit_for(name: str) -> FakeTransit:
    return FakeTransit()


def _doc(session, key="documents/a"):
    doc = register(session, key)
    session.flush()
    return doc


def _store():
    return OriginalsStore(InMemoryObjectStore(), DocumentKeys(_transit_for))


# --- PutResult has no truthiness --------------------------------------------

def test_put_result_has_no_truthiness():
    for member in PutResult:
        with pytest.raises(TypeError):
            bool(member)


# --- round trip --------------------------------------------------------------

def test_round_trip(session):
    store = _store()
    doc = _doc(session)
    assert store.put_original(session, doc.id, doc.object_key, b"the pdf bytes") is PutResult.WROTE
    assert store.get_original(session, doc.object_key) == b"the pdf bytes"


# --- the five rules of put_original ------------------------------------------

def test_rule1_reingest_with_matching_object_is_unchanged_and_moves_owner(session):
    store = _store()
    doc1 = _doc(session, "documents/a")
    assert store.put_original(session, doc1.id, doc1.object_key, b"hello") is PutResult.WROTE
    session.commit()

    doc2 = _doc(session, "documents/b")
    result = store.put_original(session, doc2.id, doc1.object_key, b"hello")
    assert result is PutResult.UNCHANGED
    row = session.get(DocumentKeyRecord, doc1.object_key)
    assert row.document_id == doc2.id
    assert store.get_original(session, doc1.object_key) == b"hello"


def test_rule2_missing_object_is_resealed_under_the_same_key(session):
    store = _store()
    doc = _doc(session)
    store.put_original(session, doc.id, doc.object_key, b"hello")
    session.commit()
    key_id_before = session.get(DocumentKeyRecord, doc.object_key).key_id
    store.objects.delete(doc.object_key)

    result = store.put_original(session, doc.id, doc.object_key, b"hello")
    assert result is PutResult.WROTE
    assert session.get(DocumentKeyRecord, doc.object_key).key_id == key_id_before
    assert store.get_original(session, doc.object_key) == b"hello"


def test_rule2_object_with_stale_key_id_is_rewritten(session):
    store = _store()
    doc = _doc(session)
    store.put_original(session, doc.id, doc.object_key, b"hello")
    session.commit()
    key_id_before = session.get(DocumentKeyRecord, doc.object_key).key_id
    stale = seal(os.urandom(32), "f" * 12, doc.object_key, b"stale bytes")
    store.objects.put(doc.object_key, stale)

    result = store.put_original(session, doc.id, doc.object_key, b"hello")
    assert result is PutResult.WROTE
    assert session.get(DocumentKeyRecord, doc.object_key).key_id == key_id_before
    assert store.get_original(session, doc.object_key) == b"hello"


def test_rule3_orphan_sealed_object_with_no_row_gets_a_new_row(session):
    store = _store()
    doc = _doc(session)
    orphan = seal(os.urandom(32), "g" * 12, doc.object_key, b"orphan bytes")
    store.objects.put(doc.object_key, orphan)
    assert session.get(DocumentKeyRecord, doc.object_key) is None

    result = store.put_original(session, doc.id, doc.object_key, b"hello")
    assert result is PutResult.WROTE
    assert session.get(DocumentKeyRecord, doc.object_key) is not None
    assert store.get_original(session, doc.object_key) == b"hello"


def test_rule3_no_row_no_object_mints_and_writes(session):
    store = _store()
    doc = _doc(session)
    result = store.put_original(session, doc.id, doc.object_key, b"hello")
    assert result is PutResult.WROTE
    assert store.get_original(session, doc.object_key) == b"hello"


def test_rule4_legacy_object_with_no_row_is_left_alone(session):
    store = _store()
    doc = _doc(session)
    store.objects.put(doc.object_key, b"%PDF-1.4 legacy plaintext")
    result = store.put_original(session, doc.id, doc.object_key, b"hello")
    assert result is PutResult.LEGACY
    assert store.objects.get(doc.object_key) == b"%PDF-1.4 legacy plaintext"
    assert session.get(DocumentKeyRecord, doc.object_key) is None


def test_rule4_legacy_object_with_pending_row_is_left_alone(session):
    store = _store()
    doc = _doc(session)
    store.objects.put(doc.object_key, b"%PDF-1.4 legacy plaintext")
    store._keys.mint(session, doc.id, doc.object_key, "_global")
    session.flush()
    result = store.put_original(session, doc.id, doc.object_key, b"hello")
    assert result is PutResult.LEGACY
    assert store.objects.get(doc.object_key) == b"%PDF-1.4 legacy plaintext"
    assert session.get(DocumentKeyRecord, doc.object_key).sealed_at is None


def test_rule5_downgrade_raises_and_writes_nothing(session):
    store = _store()
    doc = _doc(session)
    store.put_original(session, doc.id, doc.object_key, b"hello")
    session.commit()
    store.objects.put(doc.object_key, b"%PDF-1.4 downgraded to plaintext")

    with pytest.raises(SealedObjectError):
        store.put_original(session, doc.id, doc.object_key, b"new bytes")
    assert store.objects.get(doc.object_key) == b"%PDF-1.4 downgraded to plaintext"


# --- concurrency: two first writes of one object (task 3.1) ----------------

def test_two_concurrent_first_writes_end_with_one_row_and_an_object_that_opens(
        session_factory):
    objects = InMemoryObjectStore()
    keys = DocumentKeys(_transit_for)
    store = OriginalsStore(objects, keys)

    with session_factory() as s:
        doc = register(s, "documents/race")
        s.commit()
        doc_id, object_key = doc.id, doc.object_key

    begun = threading.Event()
    done = threading.Event()
    outcome = {}

    def second_writer():
        try:
            with session_factory() as s2:
                begun.wait(5)
                outcome["result"] = store.put_original(s2, doc_id, object_key, b"race bytes")
                s2.commit()
        except Exception as exc:  # pragma: no cover -- the failure is the finding
            outcome["error"] = exc
        finally:
            done.set()

    s1 = session_factory()
    try:
        result1 = store.put_original(s1, doc_id, object_key, b"race bytes")  # uncommitted
        t = threading.Thread(target=second_writer)
        t.start()
        begun.set()
        time.sleep(0.3)  # the second writer is now blocked on the primary key
        s1.commit()
        done.wait(10)
        t.join(5)
    finally:
        s1.close()

    assert "error" not in outcome, outcome.get("error")
    assert result1 is PutResult.WROTE
    assert outcome["result"] is PutResult.WROTE
    with session_factory() as s:
        rows = s.execute(
            select(DocumentKeyRecord).where(DocumentKeyRecord.object_key == object_key)
        ).scalars().all()
        assert len(rows) == 1
        assert store.get_original(s, object_key) == b"race bytes"


# --- crash analysis: task 3.2, five tests -----------------------------------

class _RaisingPutStore(InMemoryObjectStore):
    def put(self, key, data):
        raise ObjectStoreError("put failed")


def test_crash_a_store_that_raises_on_put_leaves_no_row_and_no_object(session):
    store = OriginalsStore(_RaisingPutStore(), DocumentKeys(_transit_for))
    doc = _doc(session)
    with pytest.raises(ObjectStoreError):
        store.put_original(session, doc.id, doc.object_key, b"hello")
    session.rollback()
    with pytest.raises(ObjectStoreError):
        store.objects.get(doc.object_key)


def test_crash_b_wrote_then_failed_commit_is_repaired_by_a_fresh_write(session_factory):
    objects = InMemoryObjectStore()
    store = OriginalsStore(objects, DocumentKeys(_transit_for))
    with session_factory() as s:
        doc = register(s, "documents/crash-b")
        s.commit()
        doc_id, object_key = doc.id, doc.object_key

    with session_factory() as s:
        result = store.put_original(s, doc_id, object_key, b"hello")
        assert result is PutResult.WROTE
        s.rollback()  # the caller's commit failed
        if result is PutResult.WROTE:
            store.objects.delete(object_key)  # the caller's contract

    with session_factory() as s:
        assert s.get(DocumentKeyRecord, object_key) is None
    assert not store.objects.exists(object_key)

    with session_factory() as s:
        result2 = store.put_original(s, doc_id, object_key, b"hello")
        assert result2 is PutResult.WROTE
        s.commit()
        assert store.get_original(s, object_key) == b"hello"


def test_crash_c_unreachable_key_service_writes_nothing(session):
    class BoomTransit:
        def wrap(self, plaintext):
            raise RuntimeError("key service down")

        def unwrap(self, ciphertext):
            raise RuntimeError("key service down")

    store = OriginalsStore(InMemoryObjectStore(), DocumentKeys(lambda name: BoomTransit()))
    doc = _doc(session)
    with pytest.raises(OriginalsKeyUnavailable):
        store.put_original(session, doc.id, doc.object_key, b"hello")
    assert session.get(DocumentKeyRecord, doc.object_key) is None
    assert not store.objects.exists(doc.object_key)


def test_crash_d_legacy_plus_failed_commit_keeps_the_object(session):
    store = _store()
    doc = _doc(session)
    store.objects.put(doc.object_key, b"%PDF-1.4 legacy")
    result = store.put_original(session, doc.id, doc.object_key, b"new bytes")
    assert result is PutResult.LEGACY
    session.rollback()  # the caller's commit failed
    if result is PutResult.WROTE:
        store.objects.delete(doc.object_key)  # never reached for LEGACY
    assert store.objects.get(doc.object_key) == b"%PDF-1.4 legacy"


def test_crash_e_wrote_plus_failed_commit_deletes_the_object(session_factory):
    objects = InMemoryObjectStore()
    store = OriginalsStore(objects, DocumentKeys(_transit_for))
    with session_factory() as s:
        doc = register(s, "documents/crash-e")
        s.commit()
        doc_id, object_key = doc.id, doc.object_key

    with session_factory() as s:
        result = store.put_original(s, doc_id, object_key, b"hello")
        assert result is PutResult.WROTE
        s.rollback()  # the caller's commit failed
        if result is PutResult.WROTE:
            store.objects.delete(object_key)  # the caller's contract
    assert not objects.exists(object_key)


# --- the downgrade guard on get_original (task 3.4) -------------------------

def test_get_original_refuses_a_downgraded_object(session):
    store = _store()
    doc = _doc(session)
    store.put_original(session, doc.id, doc.object_key, b"hello")
    session.commit()
    store.objects.put(doc.object_key, b"%PDF-1.4 downgraded")
    with pytest.raises(SealedObjectError):
        store.get_original(session, doc.object_key)


def test_get_original_returns_a_legacy_object_as_is(session):
    store = _store()
    doc = _doc(session)
    store.objects.put(doc.object_key, b"%PDF-1.4 legacy")
    assert store.get_original(session, doc.object_key) == b"%PDF-1.4 legacy"


def test_get_original_returns_an_object_whose_row_is_not_yet_sealed(session):
    store = _store()
    doc = _doc(session)
    store.objects.put(doc.object_key, b"%PDF-1.4 legacy")
    store._keys.mint(session, doc.id, doc.object_key, "_global")
    session.flush()
    assert store.get_original(session, doc.object_key) == b"%PDF-1.4 legacy"
