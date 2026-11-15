# SPDX-License-Identifier: MIT
"""`wordsworth-seal-originals` (`originals-encrypt-existing`): dry run,
verify-before-replace, idempotency/resumability, the before/after report, the
`--verify` mode, sealing a live recovered document's scan, and a scan that is
gone from the store being reported `gone` rather than `failed` (#481)."""
from __future__ import annotations

import hashlib
import json

import pytest
from scan_setup import recover_document

from wordsworth.document_keys import DocumentKeyRecord, DocumentKeys
from wordsworth.object_store import InMemoryObjectStore, ObjectStoreError
from wordsworth.originals_seal import candidates, is_sealed, seal_one
from wordsworth.originals_seal_cli import run, verify
from wordsworth.originals_store import OriginalsStore
from wordsworth.pipeline import register
from wordsworth.transit import FakeTransit


def _keys() -> DocumentKeys:
    return DocumentKeys(lambda name: FakeTransit())


def _ca_key(data: bytes) -> str:
    return "documents/" + hashlib.sha256(data).hexdigest()


def _register_legacy(session_factory, store, data: bytes):
    key = _ca_key(data)
    with session_factory() as s:
        doc = register(s, key)
        s.commit()
        doc_id = doc.id
    store.put(key, data)
    return doc_id, key


# --- dry run -----------------------------------------------------------------

def test_dry_run_reports_what_would_be_sealed_and_changes_nothing(session_factory):
    store = InMemoryObjectStore()
    data = b"%PDF-1.4 legacy plaintext document one"
    doc_id, key = _register_legacy(session_factory, store, data)

    report = run(session_factory, store, _keys(), dry_run=True)

    assert report["applied"] is False
    assert {"document_id": str(doc_id), "object_key": key, "kind": "original"} \
        in report["would_seal"]
    assert store.get_raw(key) == data
    with session_factory() as s:
        assert s.get(DocumentKeyRecord, key) is None


# --- verify-before-replace ----------------------------------------------------

class _CorruptingTempStore(InMemoryObjectStore):
    """Flips a byte of whatever is written under the temporary key -- the
    sealed copy fails to open, before the plaintext original is ever
    touched."""

    def put(self, key: str, data: bytes) -> None:
        if key.startswith("sealing/"):
            data = data[:-1] + bytes([data[-1] ^ 0xFF])
        super().put(key, data)


def test_a_sealed_copy_that_fails_to_verify_leaves_the_plaintext_in_place(session_factory):
    store = _CorruptingTempStore()
    data = b"%PDF-1.4 content that must never be lost " * 5
    doc_id, key = _register_legacy(session_factory, store, data)

    outcome = seal_one(session_factory, store, _keys(), doc_id, key)

    assert outcome["status"] == "failed"
    assert store.get_raw(key) == data
    with session_factory() as s:
        row = s.get(DocumentKeyRecord, key)
        assert row is not None and row.sealed_at is None


# --- idempotent and resumable -------------------------------------------------

def test_a_second_run_reports_already_sealed_instead_of_sealing_again(session_factory):
    store = InMemoryObjectStore()
    data = b"%PDF-1.4 idempotent corpus document " * 3
    doc_id, key = _register_legacy(session_factory, store, data)
    keys = _keys()

    first = run(session_factory, store, keys, dry_run=False)
    assert first["sealed"] == 1
    assert first["failed"] == 0

    second = run(session_factory, store, keys, dry_run=False)
    assert second["sealed"] == 0
    assert second["failed"] == 0
    statuses = {r["object_key"]: r["status"] for r in second["results"]}
    assert statuses[key] == "already_sealed"

    with session_factory() as s:
        assert OriginalsStore(store, keys).get_original(s, key) == data


def test_a_run_interrupted_before_the_temporary_write_is_resumed(session_factory, monkeypatch):
    store = InMemoryObjectStore()
    data = b"%PDF-1.4 interrupted corpus document " * 3
    doc_id, key = _register_legacy(session_factory, store, data)
    keys = _keys()

    import wordsworth.originals_seal as mod

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated crash before the temporary write")

    monkeypatch.setattr(mod.originals_envelope, "seal", _boom)
    with pytest.raises(RuntimeError, match="simulated crash"):
        seal_one(session_factory, store, keys, doc_id, key)
    monkeypatch.undo()

    # The row was minted and committed; the plaintext is untouched.
    with session_factory() as s:
        row = s.get(DocumentKeyRecord, key)
        assert row is not None and row.sealed_at is None
    assert store.get_raw(key) == data

    outcome = seal_one(session_factory, store, keys, doc_id, key)
    assert outcome["status"] == "sealed"
    with session_factory() as s:
        assert s.get(DocumentKeyRecord, key).sealed_at is not None
        assert OriginalsStore(store, keys).get_original(s, key) == data


# --- the before/after report --------------------------------------------------

def test_before_after_counts_and_bytes_report_carries_no_content(session_factory):
    store = InMemoryObjectStore()
    secret = "Dit mag nooit in het rapport staan, geheime inhoud."
    data = f"%PDF-1.4 {secret}".encode() * 2
    doc_id, key = _register_legacy(session_factory, store, data)

    report = run(session_factory, store, _keys(), dry_run=False)

    assert report["before"]["originals"] == {
        "objects": 1, "sealed": 0, "legacy": 1, "bytes": len(data)}
    assert report["after"]["originals"]["objects"] == 1
    assert report["after"]["originals"]["sealed"] == 1
    assert report["after"]["originals"]["legacy"] == 0
    assert report["after"]["originals"]["bytes"] > len(data)  # header overhead

    dumped = json.dumps(report, default=str)
    assert secret not in dumped


# --- no live document has a legacy original after a run; --verify -----------

def test_verify_mode_confirms_no_live_document_has_a_legacy_original(session_factory):
    store = InMemoryObjectStore()
    data = b"%PDF-1.4 verify-mode document " * 4
    _doc_id, key = _register_legacy(session_factory, store, data)

    with session_factory() as s:
        before = verify(s, store)
    assert before["ok"] is False
    assert any(c["object_key"] == key for c in before["legacy"])

    run(session_factory, store, _keys(), dry_run=False)

    with session_factory() as s:
        after = verify(s, store)
    assert after == {"ok": True, "legacy": [], "gone": []}


# --- a live recovered document's scan (#473) ---------------------------------

def test_scan_of_a_live_recovered_document_is_sealed_and_counted_separately(
        session_factory, scanned_pdf):
    store = InMemoryObjectStore()  # a plain store: ingest+recover leave it legacy
    with session_factory() as s:
        _doc_id, scan_key, ocr_key = recover_document(s, store, scanned_pdf)
        s.commit()
    assert not is_sealed(store.get_raw(scan_key))
    assert not is_sealed(store.get_raw(ocr_key))
    keys = _keys()

    report = run(session_factory, store, keys, dry_run=False)

    assert report["failed"] == 0
    assert report["scans"] == 1
    assert report["sealed"] == 2  # the recovered document's original and its scan
    assert is_sealed(store.get_raw(scan_key))
    assert is_sealed(store.get_raw(ocr_key))

    # idempotent: an already-sealed scan is left alone, not re-sealed or failed
    again = run(session_factory, store, keys, dry_run=False)
    assert again["sealed"] == 0
    assert again["scans"] == 0
    assert again["failed"] == 0


# --- a scan no longer in the store is `gone`, not `failed` (#481) -----------

def test_a_scan_missing_from_the_store_is_gone_not_a_candidate_or_a_failure(
        session_factory, scanned_pdf):
    store = InMemoryObjectStore()
    with session_factory() as s:
        _doc_id, scan_key, _ocr_key = recover_document(s, store, scanned_pdf)
        s.commit()
    store.delete(scan_key)

    with session_factory() as s:
        work, gone = candidates(s, store)
    assert any(c.object_key == scan_key for c in gone)
    assert all(c.object_key != scan_key for c in work)

    report = run(session_factory, store, _keys(), dry_run=False)
    assert report["failed"] == 0
    assert report["gone"] == 1
    assert report["sealed"] == 1  # the recovered document's own original only


class _FlakyReadStore(InMemoryObjectStore):
    """`exists` says yes (candidate-listing time) but `get_raw` raises once
    (sealing time) -- the race #481 guards against."""

    def __init__(self):
        super().__init__()
        self._boom_once: set[str] = set()

    def get_raw(self, key: str) -> bytes:
        if key in self._boom_once:
            self._boom_once.discard(key)
            raise ObjectStoreError("vanished between listing and read")
        return super().get_raw(key)


def test_a_scan_that_vanishes_between_listing_and_read_is_gone_not_failed(
        session_factory, scanned_pdf):
    """candidates() can only check `exists` at listing time (#481); the read
    itself, inside `seal_one`, is where a scan can still vanish."""
    store = _FlakyReadStore()
    with session_factory() as s:
        doc_id, scan_key, _ocr_key = recover_document(s, store, scanned_pdf)
        s.commit()
    store._boom_once.add(scan_key)

    outcome = seal_one(session_factory, store, _keys(), doc_id, scan_key)

    assert outcome == {"status": "gone"}
