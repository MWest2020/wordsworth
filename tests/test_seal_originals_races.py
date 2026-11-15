# SPDX-License-Identifier: MIT
"""Review of #484, blocking 1: a seal run beside a deletion must not bring the
deleted document back. Before the fix `seal_one` took no lock and never
re-checked: a deletion committed after the plaintext read left the run
minting a fresh key row for the deleted document and writing its object back
(case A); one committed between the mint and the overwrite left the object
written back and the run crashing on the gone key row (case B).

Now each of the seal's two transactions locks the claimant's row FOR SHARE
and re-checks the claim. A deletion that starts inside one waits for its
commit and then removes what it wrote; a deletion that commits between them,
or before the first, makes the object `skipped_deleted`. Either way the
deleted document has no key row and nothing at its keys afterwards. These
tests run a real deletion in another session against the real Postgres."""
from __future__ import annotations

import pytest
from scan_setup import recover_document, recover_now
from seal_setup import (PLAINTEXT, DeletingStore, assert_stayed_deleted, delete_now,
                        fake_keys, temp_key)

from wordsworth import originals_seal
from wordsworth.originals_seal import seal_one
from wordsworth.pipeline import ingest
from wordsworth.seal_originals import run


def _ingested(session_factory, store):
    with session_factory() as s:
        doc = ingest(s, store, PLAINTEXT)
        s.commit()
        return doc.id, doc.object_key


@pytest.mark.parametrize("op,at", [("get_raw", "final"), ("put", "temp")])
def test_a_deletion_during_the_seal_keeps_the_document_deleted(session_factory, op, at):
    """get_raw: case A (the plaintext was just read, no key row yet). put on
    the temporary key: case B (the key row is minted, the overwrite is next)."""
    store = DeletingStore(session_factory)
    document_id, object_key = _ingested(session_factory, store)
    store.arm(op, object_key if at == "final" else temp_key(object_key), document_id)

    with session_factory() as s:
        outcome = seal_one(s, store, fake_keys(), document_id, object_key)
    store.join()

    assert store.waited  # the seal held the row: the deletion could not commit inside
    assert outcome["status"] in ("sealed", "skipped_deleted")
    assert_stayed_deleted(session_factory, store, document_id, object_key)


def test_a_deletion_while_its_scan_is_sealed_keeps_the_scan_deleted(
        session_factory, scanned_pdf):
    store = DeletingStore(session_factory)
    with session_factory() as s:
        document_id, scan_key, ocr_key = recover_document(s, store, scanned_pdf)
    store.arm("get_raw", scan_key, document_id)

    with session_factory() as s:
        outcome = seal_one(s, store, fake_keys(), document_id, scan_key, "scan")
    store.join()

    assert store.waited
    assert outcome["status"] in ("sealed", "skipped_deleted")
    assert_stayed_deleted(session_factory, store, document_id, scan_key)
    assert_stayed_deleted(session_factory, store, document_id, ocr_key)


def test_a_deletion_between_mint_and_overwrite_is_skipped_deleted(
        session_factory, monkeypatch):
    """Deterministic case B: the deletion commits after the first transaction
    (the mint) and before the second one locks. Before the fix the object was
    written back and the run crashed with an AttributeError."""
    store = DeletingStore(session_factory)
    document_id, object_key = _ingested(session_factory, store)
    real, calls = originals_seal.lock_claim, []

    def delete_before_the_second(session, *args):
        calls.append(args)
        if len(calls) == 2:
            delete_now(session_factory, store, document_id)
        return real(session, *args)

    monkeypatch.setattr(originals_seal, "lock_claim", delete_before_the_second)
    report = run(session_factory, store, fake_keys(), dry_run=False)

    assert report["failed"] == 0
    assert report["done"]["skipped_deleted"] == 1
    assert [r["status"] for r in report["results"]] == ["skipped_deleted"]
    assert_stayed_deleted(session_factory, store, document_id, object_key)


def test_a_candidate_deleted_before_its_turn_is_skipped_and_its_temp_removed(
        session_factory, monkeypatch):
    """The candidate list is read once, at the start; a deletion committed
    afterwards is found by the first lock. A temporary copy a crashed run
    left for it goes too: its key is destroyed, it can never open again."""
    store = DeletingStore(session_factory)
    document_id, object_key = _ingested(session_factory, store)
    from wordsworth import seal_originals

    real_candidates, calls = seal_originals.candidates, []

    def candidates_then_delete(session, ids=None):
        work = real_candidates(session, ids)
        calls.append(ids)
        if len(calls) == 1:  # the list the run works from, not the "after" count
            session.rollback()
            store.put(temp_key(object_key), b"WWENC a temporary copy a crashed run left")
            delete_now(session_factory, store, document_id)
        return work

    monkeypatch.setattr(seal_originals, "candidates", candidates_then_delete)
    report = run(session_factory, store, fake_keys(), dry_run=False)

    assert report["failed"] == 0
    assert report["done"]["skipped_deleted"] == 1
    assert_stayed_deleted(session_factory, store, document_id, object_key)


def test_a_claim_moved_by_ocr_recovery_is_skipped_moved_and_sealed_next_run(
        session_factory, monkeypatch, mem_store, scanned_pdf):
    """Not a deletion: OCR recovery repointed the row between the two
    transactions. Reported as moved, not deleted; the next run seals the
    object under its new claim (the scan)."""
    with session_factory() as s:
        doc = ingest(s, mem_store, scanned_pdf)
        s.commit()
        document_id, scan_key = doc.id, doc.object_key
    real, calls = originals_seal.lock_claim, []

    def recover_before_the_second(session, *args):
        calls.append(args)
        if len(calls) == 2:
            with session_factory() as other:
                recover_now(other, mem_store, document_id)
        return real(session, *args)

    monkeypatch.setattr(originals_seal, "lock_claim", recover_before_the_second)
    report = run(session_factory, mem_store, fake_keys(), dry_run=False)
    assert report["failed"] == 0
    assert [r["status"] for r in report["results"]] == ["skipped_moved"]

    monkeypatch.undo()
    rerun = run(session_factory, mem_store, fake_keys(), dry_run=False)
    assert rerun["failed"] == 0 and rerun["done"]["scans"] == 1
    assert mem_store.get_raw(scan_key).startswith(b"WWENC")
