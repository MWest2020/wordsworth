# SPDX-License-Identifier: MIT
"""Review of #484, blocking 2 and the missing tests: a failure at the final key
or at the key service is one object's `failed` (exception class name only),
never the end of the run; a bad overwrite is repaired from the verified
temporary copy, by the same run or by a rerun; and the paths the review found
untested -- a sealed object with no key row, an original missing from the
store, a crash after the mint and before the temporary write."""
from __future__ import annotations

import json

from seal_setup import (MARKER, PLAINTEXT, CorruptFinalReadStore, CorruptFinalWriteStore,
                        DownTransit, fake_keys, temp_key)
from shred_setup import key_row

from wordsworth.document_keys import DocumentKeys
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.originals_envelope import HEADER_MAGIC, seal as envelope_seal
from wordsworth.originals_store import OriginalsStore
from wordsworth.pipeline import ingest
from wordsworth.seal_originals import run, verify

SECOND = b"%PDF-1.4 a second, unrelated document"


def _ingest(session_factory, store, *datas):
    with session_factory() as s:
        docs = [ingest(s, store, data) for data in datas]
        s.commit()
        return [(d.id, d.object_key) for d in docs]


def _reads_back(session_factory, store, keys, object_key) -> bytes:
    with session_factory() as s:
        return OriginalsStore(store, keys).get_original(s, object_key)


def test_a_corrupted_overwrite_is_repaired_from_the_temporary_copy(session_factory):
    store, keys = CorruptFinalWriteStore(), fake_keys()
    [(_id, object_key)] = _ingest(session_factory, store, PLAINTEXT)

    report = run(session_factory, store, keys, dry_run=False)

    assert store.corrupted == 1
    assert report["failed"] == 0 and report["done"]["sealed"] == 1
    assert not store.exists(temp_key(object_key))
    assert _reads_back(session_factory, store, keys, object_key) == PLAINTEXT


def test_a_final_key_that_never_verifies_is_failed_and_the_run_goes_on(session_factory):
    probe = InMemoryObjectStore()
    [(_i, bad_key), (_j, good_key)] = _ingest(session_factory, probe, PLAINTEXT, SECOND)
    store, keys = CorruptFinalReadStore(bad_key), fake_keys()
    for key in (bad_key, good_key):
        store.put(key, probe.get_raw(key))

    report = run(session_factory, store, keys, dry_run=False)

    by_key = {r["object_key"]: r for r in report["results"]}
    assert by_key[bad_key]["status"] == "failed"
    assert by_key[good_key]["status"] == "sealed"
    assert report["failed"] == 1
    # The plaintext is gone; the verified copy at the temporary key is kept.
    assert store.exists(temp_key(bad_key))
    with session_factory() as s:
        assert key_row(s, bad_key).sealed_at is None

    healthy = InMemoryObjectStore()  # the store's reads recover: a rerun finishes it
    for key in (bad_key, good_key, temp_key(bad_key)):
        healthy.put(key, store.get_raw(key) if key != bad_key else store._data[key])
    rerun = run(session_factory, healthy, keys, dry_run=False)
    assert rerun["failed"] == 0
    assert _reads_back(session_factory, healthy, keys, bad_key) == PLAINTEXT
    assert not healthy.exists(temp_key(bad_key))


def test_a_rerun_restores_a_bad_overwrite_from_the_temporary_copy(session_factory, mem_store):
    keys = fake_keys()
    [(document_id, object_key)] = _ingest(session_factory, mem_store, PLAINTEXT)
    with session_factory() as s:
        key = keys.mint(s, document_id, object_key, "_global")
        s.commit()
    good = envelope_seal(key.material, key.key_id, object_key, PLAINTEXT)
    mem_store.put(temp_key(object_key), good)
    mem_store.put(object_key, good[:-1] + bytes([good[-1] ^ 1]))  # the bad overwrite

    report = run(session_factory, mem_store, keys, dry_run=False)

    assert report["failed"] == 0 and report["done"]["sealed"] == 1
    assert mem_store.get_raw(object_key) == good
    assert not mem_store.exists(temp_key(object_key))
    with session_factory() as s:
        assert key_row(s, object_key).sealed_at is not None


def test_key_service_down_is_failed_by_class_name_and_changes_nothing(
        session_factory, mem_store):
    ids = _ingest(session_factory, mem_store, PLAINTEXT, SECOND)

    report = run(session_factory, mem_store, DocumentKeys(lambda name: DownTransit()),
                 dry_run=False)

    assert report["failed"] == 2
    assert {r["error"] for r in report["results"]} == {"OriginalsKeyUnavailable"}
    assert MARKER.decode() not in json.dumps(report, default=str)
    with session_factory() as s:
        for _id, object_key in ids:
            assert key_row(s, object_key) is None
            assert mem_store.get_raw(object_key) in (PLAINTEXT, SECOND)


def test_a_sealed_object_with_no_key_row_is_failed_and_fails_verify(
        session_factory, mem_store):
    [(document_id, object_key)] = _ingest(session_factory, mem_store, PLAINTEXT)
    keys = fake_keys()
    with session_factory() as s:
        key = keys.mint(s, document_id, object_key, "_global")
        s.rollback()  # the row never committed; the object below has no key
    mem_store.put(object_key, envelope_seal(key.material, key.key_id, object_key, PLAINTEXT))

    report = run(session_factory, mem_store, keys, dry_run=False)
    assert report["results"][0]["error"] == "sealed object has no key row"
    with session_factory() as s:
        checked = verify(s, mem_store)
    assert checked["verified"] is False
    assert [e["object_key"] for e in checked["no_key_row"]] == [object_key]


def test_an_original_missing_from_the_store_is_failed_and_listed(session_factory, mem_store):
    [(_id, object_key)] = _ingest(session_factory, mem_store, PLAINTEXT)
    mem_store.delete(object_key)

    report = run(session_factory, mem_store, fake_keys(), dry_run=False)
    assert report["results"][0] | {"document_id": None} == {
        "document_id": None, "object_key": object_key, "kind": "original",
        "status": "failed", "error": "missing"}
    with session_factory() as s:
        checked = verify(s, mem_store)
    assert [e["object_key"] for e in checked["missing"]] == [object_key]


def test_a_crash_after_the_mint_before_the_temporary_write_reruns_clean(
        session_factory, mem_store):
    keys = fake_keys()
    [(document_id, object_key)] = _ingest(session_factory, mem_store, PLAINTEXT)
    with session_factory() as s:
        minted = keys.mint(s, document_id, object_key, "_global")
        s.commit()  # ... and the process died here

    report = run(session_factory, mem_store, keys, dry_run=False)

    assert report["failed"] == 0 and report["done"]["sealed"] == 1
    with session_factory() as s:
        row = key_row(s, object_key)
        assert row.key_id == minted.key_id and row.sealed_at is not None
    assert mem_store.get_raw(object_key)[:len(HEADER_MAGIC)] == HEADER_MAGIC
    assert _reads_back(session_factory, mem_store, keys, object_key) == PLAINTEXT


def test_verify_lists_pending_and_fails_on_a_mismatched_key_id(session_factory, mem_store):
    keys = fake_keys()
    [(i, pending), (j, mismatched)] = _ingest(session_factory, mem_store, PLAINTEXT, SECOND)
    with session_factory() as s:
        k1 = keys.mint(s, i, pending, "_global")
        k2 = keys.mint(s, j, mismatched, "_global")
        s.commit()
    mem_store.put(pending, envelope_seal(k1.material, k1.key_id, pending, PLAINTEXT))
    mem_store.put(mismatched, envelope_seal(k2.material, "0" * 12, mismatched, SECOND))

    with session_factory() as s:
        checked = verify(s, mem_store)
    assert [e["object_key"] for e in checked["pending"]] == [pending]
    assert [e["object_key"] for e in checked["key_id_mismatch"]] == [mismatched]
    assert checked["legacy"] == [] and checked["verified"] is False
