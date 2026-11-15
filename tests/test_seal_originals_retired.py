# SPDX-License-Identifier: MIT
"""`wordsworth-seal-originals` and a scan OCR recovery retired as a copy
(#486). The OCR'd PDF turned out to be an object another document already
is, so the scan's document was superseded (`supersede(..., as_object=...)`)
and keeps its own object: no survivor shares that key and no `ocr` record
names it. Before the fix no candidate covered it -- it stayed plaintext and
`--verify` passed over it. It is sealed as a scan, under its own document's
claim, and a deleted one stays deleted."""
from __future__ import annotations

import hashlib

import pytest
from seal_setup import DeletingStore, assert_stayed_deleted, delete_now, fake_keys

from wordsworth import seal_candidates
from wordsworth.audit import current_state
from wordsworth.document_keys import DocumentKeyRecord
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.ocr import FixedOcrEngine
from wordsworth.originals_envelope import HEADER_MAGIC
from wordsworth.originals_seal import seal_one
from wordsworth.originals_store import OriginalsStore
from wordsworth.pipeline import ingest, process, register
from wordsworth.recovery import recover
from wordsworth.seal_originals import run, verify
from wordsworth.states import State
from wordsworth.supersession import supersede

_OWNED_PDF = FixedOcrEngine("Deze tekst is al een ander levend document. " * 3).ocr(b"%PDF-1.4")
_OWNED_KEY = "documents/" + hashlib.sha256(_OWNED_PDF).hexdigest()


class _SameOcr:
    lang = "nld"

    def ocr(self, pdf_bytes: bytes) -> bytes:
        return _OWNED_PDF


def _retired_scan(session_factory, store, scanned_pdf):
    """A live owner of the OCR'd PDF and a scan that the real `recover`
    retires as its copy, both legacy plaintext. ``(scan_id, scan_key)``."""
    with session_factory() as s:
        register(s, _OWNED_KEY)
        store.put(_OWNED_KEY, _OWNED_PDF)
        scan = ingest(s, store, scanned_pdf)
        s.commit()
        assert process(s, scan.id, store) == State.UNPROCESSABLE_OCR
        s.commit()
        assert recover(s, scan.id, store, threshold=10, engine=_SameOcr()) == State.SUPERSEDED
        s.commit()
        assert scan.object_key != _OWNED_KEY  # the copy keeps its own object
        return scan.id, scan.object_key


def _verify(session_factory, store):
    with session_factory() as s:
        return verify(s, store)


def test_retired_copy_scan_is_sealed_and_verifies(session_factory, mem_store, scanned_pdf):
    scan_id, scan_key = _retired_scan(session_factory, mem_store, scanned_pdf)
    keys = fake_keys()

    before = _verify(session_factory, mem_store)
    assert before["verified"] is False  # plaintext at rest is no longer passed over
    assert {"document_id": str(scan_id), "object_key": scan_key,
            "kind": "scan"} in before["legacy"]
    dry = run(session_factory, mem_store, keys, dry_run=True)
    assert sorted(dry["would_seal"]) == sorted([_OWNED_KEY, scan_key])
    assert mem_store.get_raw(scan_key) == scanned_pdf  # the dry run changed nothing

    report = run(session_factory, mem_store, keys, dry_run=False)
    assert report["failed"] == 0
    assert report["done"]["sealed"] == 1 and report["done"]["scans"] == 1
    assert {r["object_key"]: (r["kind"], r["status"]) for r in report["results"]} == {
        _OWNED_KEY: ("original", "sealed"), scan_key: ("scan", "sealed")}
    assert mem_store.get_raw(scan_key)[:len(HEADER_MAGIC)] == HEADER_MAGIC
    with session_factory() as s:
        row = s.get(DocumentKeyRecord, scan_key)
        assert row.sealed_at is not None and row.document_id == scan_id
        assert OriginalsStore(mem_store, keys).get_original(s, scan_key) == scanned_pdf
        assert current_state(s, scan_id) == State.SUPERSEDED  # the trail is untouched
    after = _verify(session_factory, mem_store)
    assert after["verified"] is True and after["pending"] == []

    rerun = run(session_factory, mem_store, keys, dry_run=False)
    assert rerun["done"]["already_sealed"] == 2 and rerun["failed"] == 0


def test_only_ids_of_the_retired_copy_seals_its_scan(session_factory, mem_store, scanned_pdf):
    scan_id, scan_key = _retired_scan(session_factory, mem_store, scanned_pdf)

    report = run(session_factory, mem_store, fake_keys(), dry_run=False, ids=[scan_id])
    assert [(r["object_key"], r["status"]) for r in report["results"]] == [(scan_key, "sealed")]
    assert mem_store.get_raw(_OWNED_KEY) == _OWNED_PDF


def test_a_deleted_retired_copy_is_no_candidate(session_factory, mem_store, scanned_pdf):
    scan_id, scan_key = _retired_scan(session_factory, mem_store, scanned_pdf)
    delete_now(session_factory, mem_store, scan_id)

    report = run(session_factory, mem_store, fake_keys(), dry_run=False)
    assert [r["object_key"] for r in report["results"]] == [_OWNED_KEY]
    assert_stayed_deleted(session_factory, mem_store, scan_id, scan_key)


def test_a_retired_copy_deleted_after_the_candidate_list_stays_deleted(
        session_factory, mem_store, scanned_pdf):
    """The list is read once; the deletion commits before the seal's lock."""
    scan_id, scan_key = _retired_scan(session_factory, mem_store, scanned_pdf)
    with session_factory() as s:
        assert seal_candidates.lock_claim(s, scan_id, scan_key, "scan")
    delete_now(session_factory, mem_store, scan_id)

    with session_factory() as s:
        outcome = seal_one(s, mem_store, fake_keys(), scan_id, scan_key, "scan")
    assert outcome == {"status": "skipped_deleted"}
    assert_stayed_deleted(session_factory, mem_store, scan_id, scan_key)


def test_a_deletion_while_a_retired_scan_is_sealed_keeps_it_deleted(
        session_factory, scanned_pdf):
    store = DeletingStore(session_factory)
    scan_id, scan_key = _retired_scan(session_factory, store, scanned_pdf)
    store.arm("get_raw", scan_key, scan_id)

    with session_factory() as s:
        outcome = seal_one(s, store, fake_keys(), scan_id, scan_key, "scan")
    store.join()

    assert store.waited  # the seal held the row: the deletion waited for its commit
    assert outcome["status"] in ("sealed", "skipped_deleted")
    assert_stayed_deleted(session_factory, store, scan_id, scan_key)


def test_a_retired_scan_no_longer_in_the_store_is_gone(session_factory, mem_store,
                                                       scanned_pdf):
    _scan_id, scan_key = _retired_scan(session_factory, mem_store, scanned_pdf)
    mem_store.delete(scan_key)

    report = run(session_factory, mem_store, fake_keys(), dry_run=False)
    assert report["failed"] == 0 and report["done"]["gone"] == 1
    assert _verify(session_factory, mem_store)["verified"] is True


@pytest.mark.parametrize("kind", ["original", "scan"])
def test_an_ordinary_copy_adds_no_candidate_and_claims_no_scan(legacy_copies, kind):
    """A copy that shares its survivor's key (no `as_object`) is covered by
    the survivor's original, and is never a claimant of it as a scan."""
    store = InMemoryObjectStore()
    with legacy_copies() as s:
        survivor = ingest(s, store, b"%PDF-1.4 one object, two documents")
        copy = register(s, survivor.object_key)
        s.commit()
        supersede(s, copy.id, survivor.id, actor="t")
        s.commit()
        key, copy_id, survivor_id = survivor.object_key, copy.id, survivor.id
        found = seal_candidates.candidates(s)
        assert [(c.document_id, c.object_key, c.kind) for c in found] == [
            (survivor_id, key, "original")]
        assert seal_candidates.lock_claim(s, copy_id, key, kind) is (kind == "original")
