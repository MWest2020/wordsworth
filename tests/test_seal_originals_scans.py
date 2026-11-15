# SPDX-License-Identifier: MIT
"""`wordsworth-seal-originals` and the original scan of an OCR-recovered
document that is not deleted (#473): sealed too, counted separately as a
scan; left alone when already sealed or gone; and a superseded copy's scan
counts, as the spec counts a superseded copy as not deleted (review of #484)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from scan_setup import recover_document, recover_now

from wordsworth.document_keys import DocumentKeyRecord, DocumentKeys
from wordsworth.originals_envelope import HEADER_MAGIC, seal as envelope_seal
from wordsworth.pipeline import ingest, register
from wordsworth.seal_originals import run
from wordsworth.supersession import supersede
from wordsworth.transit import FakeTransit


@pytest.fixture
def keys():
    return DocumentKeys(lambda name: FakeTransit())


def _pre_seal(session, store, keys, document_id, object_key: str) -> None:
    """Seal ``object_key`` ahead of the run, as a prior run would have left
    it: row minted, bytes sealed and replaced, ``sealed_at`` committed."""
    key = keys.mint(session, document_id, object_key, "_global")
    session.commit()
    data = store.get_raw(object_key)
    store.put(object_key, envelope_seal(key.material, key.key_id, object_key, data))
    row = session.get(DocumentKeyRecord, object_key)
    row.sealed_at = datetime.now(timezone.utc)
    session.commit()


def test_scan_of_a_live_recovered_document_is_sealed_counted_as_scan(
        session_factory, mem_store, keys, scanned_pdf):
    with session_factory() as session:
        _doc_id, scan_key, ocr_key = recover_document(session, mem_store, scanned_pdf)

    report = run(session_factory, mem_store, keys, dry_run=False)
    assert report["done"]["sealed"] == 1  # the recovered document's own (OCR'd) original
    assert report["done"]["scans"] == 1   # its original scan, counted separately
    kinds = {r["object_key"]: r["kind"] for r in report["results"]}
    assert kinds[scan_key] == "scan"
    assert kinds[ocr_key] == "original"
    assert mem_store.get_raw(scan_key)[:len(HEADER_MAGIC)] == HEADER_MAGIC


def test_scan_already_sealed_is_left_alone(session_factory, mem_store, keys, scanned_pdf):
    with session_factory() as session:
        doc_id, scan_key, _ocr_key = recover_document(session, mem_store, scanned_pdf)
        _pre_seal(session, mem_store, keys, doc_id, scan_key)
    sealed_before = mem_store.get_raw(scan_key)

    report = run(session_factory, mem_store, keys, dry_run=False)
    scan_result = next(r for r in report["results"] if r["object_key"] == scan_key)
    assert scan_result["status"] == "already_sealed"
    assert mem_store.get_raw(scan_key) == sealed_before


def test_scan_no_longer_in_the_store_is_left_alone(session_factory, mem_store, keys, scanned_pdf):
    """Review of the build (#481): a live recovered document whose scan is gone
    from the store is nothing to seal and nothing failed."""
    with session_factory() as session:
        _doc_id, scan_key, _ocr_key = recover_document(session, mem_store, scanned_pdf)
    mem_store.delete(scan_key)

    report = run(session_factory, mem_store, keys, dry_run=False)
    assert report["failed"] == 0
    assert report["done"]["scan_gone"] == 1
    assert not any(r["object_key"] == scan_key for r in report["results"])


def test_scan_of_a_superseded_recovered_copy_is_sealed(legacy_copies, mem_store, keys,
                                                       scanned_pdf):
    """A recovered document later retired as a copy of a document on its OCR'd
    PDF is superseded, not deleted: its scan is still a candidate."""
    with legacy_copies() as s:
        copy = ingest(s, mem_store, scanned_pdf)
        s.commit()
        scan_key = copy.object_key
        ocr_key = recover_now(s, mem_store, copy.id)
        survivor = register(s, ocr_key)
        s.commit()
        supersede(s, copy.id, survivor.id, actor="t")
        s.commit()

    report = run(legacy_copies, mem_store, keys, dry_run=False)
    assert report["failed"] == 0
    assert report["done"]["scans"] == 1
    assert mem_store.get_raw(scan_key)[:len(HEADER_MAGIC)] == HEADER_MAGIC
