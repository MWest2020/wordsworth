# SPDX-License-Identifier: MIT
"""`wordsworth-seal-originals` reads cheaply and never crashes on a read
(production, 2026-11-15: the first dry run died on a 13 MB GET that broke off
with IncompleteRead, the second ran over ten minutes downloading everything).
Classifying -- the counts, the dry run, `--verify` -- reads a HEAD and the
sealed header only; only a real seal reads an object in full, retried once."""
from __future__ import annotations

import pytest
from s3_fake import FakeS3Client
from seal_setup import PLAINTEXT, fake_keys

from wordsworth import seal_candidates
from wordsworth.document_keys import DocumentKeyRecord
from wordsworth.object_store import InMemoryObjectStore, ObjectStoreError, S3ObjectStore
from wordsworth.originals_envelope import HEADER_MAGIC
from wordsworth.pipeline import ingest
from wordsworth.seal_originals import run, verify

SECOND = b"%PDF-1.4 a second, unrelated document"
THIRD = b"%PDF-1.4 a third document, whose object is gone"


@pytest.fixture(autouse=True)
def _no_retry_pause(monkeypatch):
    monkeypatch.setattr(seal_candidates, "RETRY_PAUSE", 0)


def _ingest(session_factory, store, *contents):
    with session_factory() as s:
        docs = [ingest(s, store, data) for data in contents]
        s.commit()
        return [(d.id, d.object_key) for d in docs]


class CountingStore(InMemoryObjectStore):
    def __init__(self):
        super().__init__()
        self.full_reads: list[str] = []

    def get_raw(self, key):
        self.full_reads.append(key)
        return super().get_raw(key)


class DownStore(InMemoryObjectStore):
    """Once ``down`` is set, every read raises it -- a store that answers
    nothing, with an error that may not even be an ObjectStoreError."""

    down: Exception | None = None

    def _raise(self):
        if self.down is not None:
            raise self.down

    def get_raw(self, key):
        self._raise()
        return super().get_raw(key)

    def get_head(self, key, n):
        self._raise()
        return super().get_head(key, n)

    def size(self, key):
        self._raise()
        return super().size(key)


def test_dry_run_never_reads_an_object_in_full(session_factory):
    store = CountingStore()
    _ingest(session_factory, store, PLAINTEXT, SECOND)
    store.full_reads.clear()

    report = run(session_factory, store, fake_keys(), dry_run=True)
    assert report["before"]["legacy"] == 2
    assert len(report["would_seal"]) == 2
    assert store.full_reads == []


def test_a_real_run_reads_each_original_in_full_once_before_sealing(session_factory):
    store = CountingStore()
    [(_id, key)] = _ingest(session_factory, store, PLAINTEXT)
    store.full_reads.clear()
    store.put = lambda k, d, put=store.put: (store.full_reads.append(f"put {k}"), put(k, d))

    report = run(session_factory, store, fake_keys(), dry_run=False)
    assert report["done"]["sealed"] == 1
    assert store.full_reads[:store.full_reads.index(f"put {key}")].count(key) == 1


def test_broken_full_reads_dry_run_finishes_and_classifies(session_factory):
    """Full GETs break mid-body (IncompleteRead), ranged reads work: the dry
    run classifies every object; a real run reports the unreadable original
    as failed and goes on."""
    client = FakeS3Client()
    store = S3ObjectStore(client, "bucket")
    (one, k1), (_two, k2), (_three, k3) = _ingest(session_factory, store,
                                                  PLAINTEXT, SECOND, THIRD)
    assert run(session_factory, store, fake_keys(), dry_run=False,
               ids=[one])["done"]["sealed"] == 1
    del client.objects[k3]
    client.break_full_reads = True
    client.calls.clear()

    report = run(session_factory, store, fake_keys(), dry_run=True)
    assert report["before"] | {"bytes": 0} == {
        "objects": 3, "sealed": 1, "legacy": 1, "missing": 1, "unreadable": 0, "bytes": 0}
    assert report["would_seal"] == [k2] and report["unreadable"] == []
    assert client.full_gets() == []

    real = run(session_factory, store, fake_keys(), dry_run=False)
    outcome = {r["object_key"]: (r["status"], r.get("error")) for r in real["results"]}
    assert set(outcome) == {k1, k2, k3}  # the run went through every object
    assert outcome[k2] == ("failed", "unreadable")
    assert outcome[k3] == ("failed", "missing")
    assert client.full_gets().count(k2) == 2  # one retry, then failed
    assert client.objects[k2] == SECOND  # the plaintext is untouched


@pytest.mark.parametrize("error", [ObjectStoreError("unreachable"),
                                   ConnectionResetError("reset by peer")])
def test_a_store_that_never_answers_is_unreadable_not_missing(session_factory, error):
    store = DownStore()
    [(_id, key)] = _ingest(session_factory, store, PLAINTEXT)
    store.down = error

    report = run(session_factory, store, fake_keys(), dry_run=True)
    assert report["before"]["unreadable"] == 1 and report["before"]["missing"] == 0
    assert report["unreadable"] == [key] and report["would_seal"] == []

    with session_factory() as s:
        checked = verify(s, store)
    assert [e["object_key"] for e in checked["unreadable"]] == [key]
    assert checked["missing"] == [] and checked["verified"] is False

    real = run(session_factory, store, fake_keys(), dry_run=False)
    assert real["failed"] == 1
    assert real["results"][0]["status"] == "failed"
    assert real["after"]["unreadable"] == 1


def test_one_transient_read_error_is_retried(session_factory):
    class FlakyStore(InMemoryObjectStore):
        flaky: set[str] = set()

        def get_raw(self, key):
            if key in self.flaky:
                self.flaky.discard(key)
                raise ObjectStoreError(f"get {key!r} failed: IncompleteRead")
            return super().get_raw(key)

    store = FlakyStore()
    [(_id, key)] = _ingest(session_factory, store, PLAINTEXT)
    store.flaky = {key}

    report = run(session_factory, store, fake_keys(), dry_run=False)
    assert report["failed"] == 0 and report["done"]["sealed"] == 1
    assert store.get_raw(key)[:len(HEADER_MAGIC)] == HEADER_MAGIC


def _seal_then_rerun(session_factory, store, forget):
    ids = _ingest(session_factory, store, PLAINTEXT, SECOND)
    keys = fake_keys()
    assert run(session_factory, store, keys, dry_run=False)["done"]["sealed"] == 2
    forget()
    return [key for _id, key in ids], run(session_factory, store, keys, dry_run=False)


def test_a_rerun_reads_only_the_header_of_a_sealed_object(session_factory):
    """#491: a rerun used to download every sealed object in full before it
    noticed `sealed_at`. Against the S3 driver: ranged GETs and HEADs only."""
    client = FakeS3Client()
    store = S3ObjectStore(client, "bucket")
    sealed, rerun = _seal_then_rerun(session_factory, store, client.calls.clear)

    assert rerun["done"] == {"sealed": 0, "scans": 0, "already_sealed": 2, "gone": 0,
                             "skipped_deleted": 0, "skipped_moved": 0, "failed": 0}
    assert client.full_gets() == []
    ranged = [(key, rng) for op, key, rng in client.calls if op == "get"]
    assert sorted(set(ranged)) == sorted((key, "bytes=0-29") for key in sealed)
    assert not [call for call in client.calls if call[0] == "put"]


def test_a_rerun_still_reads_what_is_not_sealed_and_committed(session_factory):
    """The short cut needs the header AND `sealed_at`: plaintext under a sealed
    row is read and refused (a downgrade); a pending object is read and verified."""
    store = CountingStore()
    (downgraded, pending), _ = _seal_then_rerun(session_factory, store, lambda: None)
    store.put(downgraded, PLAINTEXT)
    with session_factory() as s:
        s.get(DocumentKeyRecord, pending).sealed_at = None
        s.commit()
    store.full_reads.clear()

    report = run(session_factory, store, fake_keys(), dry_run=False)
    outcome = {r["object_key"]: (r["status"], r.get("error")) for r in report["results"]}
    assert outcome[downgraded] == ("failed", "key row is sealed but the object is plaintext")
    assert outcome[pending] == ("sealed", None)
    assert sorted(store.full_reads) == sorted([downgraded, pending])
    assert store.get_raw(downgraded) == PLAINTEXT  # nothing written over it
