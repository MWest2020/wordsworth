# SPDX-License-Identifier: MIT
"""`delete-removes-original-scan` task 3: deleting a recovered document also
removes its original scan object, under the claim (`test_delete_scan_claim.py`)
and counted as `original_scan`."""
from __future__ import annotations

import pytest

from shred_setup import key_row, originals
from scan_setup import recover_document, recover_now

from wordsworth.audit import current_state
from wordsworth.deletion import delete_document
from wordsworth.pipeline import ingest, register
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State
from wordsworth.supersession import supersede


def test_a_recovered_document_loses_both_objects_and_both_keys(session, scanned_pdf):
    store = originals()
    doc_id, scan_key, ocr_key = recover_document(session, store, scanned_pdf)
    assert store.objects.exists(scan_key) and store.objects.exists(ocr_key)
    assert key_row(session, scan_key) and key_row(session, ocr_key)

    counts = delete_document(session, doc_id, store, InMemoryIndex(), actor="t")
    session.commit()

    assert counts.object == 1 and counts.original_scan == 1 and counts.keys_destroyed == 2
    assert not store.objects.exists(scan_key) and not store.objects.exists(ocr_key)
    assert key_row(session, scan_key) is None and key_row(session, ocr_key) is None


def test_a_legacy_plaintext_scan_is_removed_without_a_key(session, scanned_pdf):
    """The scan was ingested as legacy plaintext (no key row); its OCR'd PDF
    is sealed. Only the OCR'd PDF's key is destroyed."""
    sealed_store = originals()
    plain = sealed_store.objects
    doc = ingest(session, plain, scanned_pdf)
    session.commit()
    scan_key = doc.object_key
    assert key_row(session, scan_key) is None  # never sealed
    ocr_key = recover_now(session, sealed_store, doc.id)
    assert key_row(session, ocr_key) is not None

    counts = delete_document(session, doc.id, sealed_store, InMemoryIndex(), actor="t")
    session.commit()

    assert not plain.exists(scan_key)
    assert counts.original_scan == 1 and counts.keys_destroyed == 1
    assert key_row(session, ocr_key) is None


def test_a_scan_no_longer_in_the_store_counts_zero_and_does_not_fail(
        session, scanned_pdf):
    store = originals()
    doc_id, scan_key, ocr_key = recover_document(session, store, scanned_pdf)
    store.objects.delete(scan_key)

    counts = delete_document(session, doc_id, store, InMemoryIndex(), actor="t")
    session.commit()

    assert counts.original_scan == 0
    assert counts.keys_destroyed == 2  # the key row still goes with the (missing) object


def test_a_copy_still_pointing_at_the_scan_keeps_it(legacy_copies, scanned_pdf):
    """Delete the recovered document first (the copy, outside the deletion,
    still claims S): it stays. Delete the copy afterwards: both go."""
    store = originals()
    with legacy_copies() as s:
        survivor = ingest(s, store, scanned_pdf)
        s.commit()
        scan_key = survivor.object_key
        copy = register(s, scan_key)
        s.commit()
        supersede(s, copy.id, survivor.id, actor="t")
        s.commit()
        recover_now(s, store, survivor.id)
        survivor_id, copy_id = survivor.id, copy.id

    with legacy_copies() as s:
        first = delete_document(s, survivor_id, store, InMemoryIndex(), actor="t")
        s.commit()
        assert first.original_scan == 0
        assert store.objects.exists(scan_key) and key_row(s, scan_key) is not None

        second = delete_document(s, copy_id, store, InMemoryIndex(), actor="t")
        s.commit()
        assert second.object == 1 and second.keys_destroyed == 1
        assert not store.objects.exists(scan_key) and key_row(s, scan_key) is None


def test_a_live_re_ingest_keeps_the_scan(session_factory, scanned_pdf):
    store = originals()
    with session_factory() as s:
        a = ingest(s, store, scanned_pdf)
        s.commit()
        scan_key = a.object_key
        recover_now(s, store, a.id)
        ingest(s, store, scanned_pdf)  # N: a later ingest of the scan's bytes
        s.commit()

        counts = delete_document(s, a.id, store, InMemoryIndex(), actor="t")
        s.commit()

        assert counts.original_scan == 0
        assert store.objects.exists(scan_key) and key_row(s, scan_key) is not None


def test_a_failure_removing_the_scan_is_a_hard_error_and_a_rerun_finishes(
        session, scanned_pdf, monkeypatch):
    store = originals()
    doc_id, scan_key, ocr_key = recover_document(session, store, scanned_pdf)

    real_delete = store.objects.delete

    def refuse(key):
        if key == scan_key:
            raise RuntimeError("scan removal failed")
        return real_delete(key)
    monkeypatch.setattr(store.objects, "delete", refuse)

    with pytest.raises(RuntimeError):
        delete_document(session, doc_id, store, InMemoryIndex(), actor="t")
    session.rollback()
    assert store.objects.exists(scan_key)
    assert key_row(session, scan_key) is not None

    monkeypatch.undo()
    counts = delete_document(session, doc_id, store, InMemoryIndex(), actor="t")
    session.commit()

    assert counts.original_scan == 1
    assert not store.objects.exists(scan_key)
    assert key_row(session, scan_key) is None


def test_the_dry_run_counts_and_removes_nothing(session, scanned_pdf):
    store = originals()
    doc_id, scan_key, ocr_key = recover_document(session, store, scanned_pdf)

    counts = delete_document(session, doc_id, store, InMemoryIndex(), actor="t",
                             dry_run=True)
    session.commit()

    assert counts.original_scan == 1
    assert store.objects.exists(scan_key) and key_row(session, scan_key) is not None
    assert current_state(session, doc_id) != State.DELETED
