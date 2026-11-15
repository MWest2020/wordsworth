# SPDX-License-Identifier: MIT
"""`wordsworth-seal-originals` (originals-encrypt-existing): dry run changes
nothing, a failed verify leaves the plaintext in place, the run is idempotent
and resumable, the report carries counts and bytes but never content, and the
original scan of a live OCR-recovered document is sealed too, counted
separately as a scan."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from scan_setup import recover_document

from wordsworth.document_keys import DocumentKeyRecord, DocumentKeys
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.originals_envelope import HEADER_MAGIC, seal as envelope_seal
from wordsworth.originals_seal import TEMP_PREFIX
from wordsworth.pipeline import ingest
from wordsworth.seal_originals import run, verify
from wordsworth.transit import FakeTransit

MARKER = b"TOTALLY-SECRET-PLAINTEXT-MARKER"
PLAINTEXT = b"%PDF-1.4 " + MARKER + b" rest of the document"


@pytest.fixture
def keys():
    return DocumentKeys(lambda name: FakeTransit())


class _CorruptingStore(InMemoryObjectStore):
    """Flips a byte of every object read back from the temporary sealing
    location -- simulates a write that silently corrupted in transit, so the
    verify-before-replace step must catch it before the plaintext is touched."""

    def get_raw(self, key):
        data = super().get_raw(key)
        if key.startswith(TEMP_PREFIX):
            corrupted = bytearray(data)
            corrupted[-1] ^= 0x01
            return bytes(corrupted)
        return data


def _digest(object_key: str) -> str:
    return object_key.rsplit("/", 1)[-1]


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


def test_dry_run_reports_and_changes_nothing(session_factory, mem_store, keys):
    with session_factory() as session:
        doc = ingest(session, mem_store, PLAINTEXT)
        session.commit()
    before_bytes = mem_store.get_raw(doc.object_key)

    report = run(session_factory, mem_store, keys, dry_run=True)
    assert report["dry_run"] is True
    assert report["before"] == {"objects": 1, "sealed": 0, "legacy": 1,
                                "missing": 0, "bytes": len(PLAINTEXT)}
    assert report["would_seal"] == [doc.object_key]
    assert mem_store.get_raw(doc.object_key) == before_bytes
    with session_factory() as session:
        assert session.get(DocumentKeyRecord, doc.object_key) is None


def test_a_failed_verify_leaves_the_plaintext_in_place(session_factory, keys):
    store = _CorruptingStore()
    with session_factory() as session:
        doc = ingest(session, store, PLAINTEXT)
        session.commit()

    report = run(session_factory, store, keys, dry_run=False)
    assert report["done"]["failed"] == 1
    assert report["results"][0]["status"] == "failed"
    assert store.get_raw(doc.object_key) == PLAINTEXT
    assert not store.exists(f"{TEMP_PREFIX}{_digest(doc.object_key)}")
    with session_factory() as session:
        row = session.get(DocumentKeyRecord, doc.object_key)
        assert row is not None  # the row before anything is written
        assert row.sealed_at is None


def test_rerun_after_sealing_reports_already_sealed_and_touches_nothing(
        session_factory, mem_store, keys):
    with session_factory() as session:
        doc = ingest(session, mem_store, PLAINTEXT)
        session.commit()

    first = run(session_factory, mem_store, keys, dry_run=False)
    assert first["done"]["sealed"] == 1
    sealed_bytes = mem_store.get_raw(doc.object_key)

    second = run(session_factory, mem_store, keys, dry_run=False)
    assert second["done"] == {"sealed": 0, "scans": 0, "already_sealed": 1, "scan_gone": 0, "failed": 0}
    assert mem_store.get_raw(doc.object_key) == sealed_bytes


def test_resumes_after_a_crash_between_overwrite_and_sealed_at_commit(
        session_factory, mem_store, keys):
    with session_factory() as session:
        doc = ingest(session, mem_store, PLAINTEXT)
        session.commit()
        document_id, object_key = doc.id, doc.object_key
        digest = _digest(object_key)

        key = keys.mint(session, document_id, object_key, "_global")
        session.commit()
    sealed = envelope_seal(key.material, key.key_id, object_key, PLAINTEXT)
    mem_store.put(f"{TEMP_PREFIX}{digest}", sealed)
    mem_store.put(object_key, sealed)  # the overwrite "happened"; sealed_at did not

    report = run(session_factory, mem_store, keys, dry_run=False)
    assert report["done"]["sealed"] == 1
    with session_factory() as session:
        assert session.get(DocumentKeyRecord, object_key).sealed_at is not None
    assert not mem_store.exists(f"{TEMP_PREFIX}{digest}")
    assert mem_store.get_raw(object_key) == sealed  # untouched, not re-sealed


def test_report_has_counts_and_bytes_never_content(session_factory, mem_store, keys):
    with session_factory() as session:
        doc = ingest(session, mem_store, PLAINTEXT)
        session.commit()

    report = run(session_factory, mem_store, keys, dry_run=False)
    assert report["before"] == {"objects": 1, "sealed": 0, "legacy": 1,
                                "missing": 0, "bytes": len(PLAINTEXT)}
    assert report["after"]["sealed"] == 1
    assert report["after"]["legacy"] == 0
    assert mem_store.get_raw(doc.object_key)[:len(HEADER_MAGIC)] == HEADER_MAGIC

    dumped = json.dumps(report, default=str)
    assert MARKER.decode() not in dumped
    assert "rest of the document" not in dumped


def test_verify_fails_before_a_run_and_passes_after(session_factory, mem_store, keys):
    with session_factory() as session:
        doc = ingest(session, mem_store, PLAINTEXT)
        session.commit()
        before = verify(session, mem_store)
    assert before["verified"] is False
    assert before["legacy"] == [{"document_id": str(doc.id), "object_key": doc.object_key,
                                 "kind": "original"}]

    run(session_factory, mem_store, keys, dry_run=False)
    with session_factory() as session:
        after = verify(session, mem_store)
    assert after == {"verified": True, "legacy": []}


def test_ids_limits_which_documents_are_considered(session_factory, mem_store, keys):
    with session_factory() as session:
        doc1 = ingest(session, mem_store, PLAINTEXT)
        doc2 = ingest(session, mem_store, b"%PDF-1.4 a second, unrelated document")
        session.commit()

    report = run(session_factory, mem_store, keys, dry_run=False, ids=[doc1.id])
    assert report["done"]["sealed"] == 1
    assert [r["document_id"] for r in report["results"]] == [str(doc1.id)]
    with session_factory() as session:
        assert session.get(DocumentKeyRecord, doc2.object_key) is None


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
