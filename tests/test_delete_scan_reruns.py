# SPDX-License-Identifier: MIT
"""`delete-removes-original-scan` task 4: a rerun over an already-deleted
document that still finds a scan removes it and records
`remove-original-scan`, `deleted` -> `deleted`, same pattern as
`destroy-key` and `remove-renders`."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from shred_setup import key_row, originals
from scan_setup import recover_document

from wordsworth import deletion_scans
from wordsworth.audit import verify_chain
from wordsworth.deletion import delete_document
from wordsworth.document_keys import DocumentKeyRecord
from wordsworth.models import AuditRecord, BoxMap
from wordsworth.pdf_redaction import redacted_cache_key
from wordsworth.search_index import InMemoryIndex


def _records(session, doc_id):
    return session.execute(
        select(AuditRecord).where(AuditRecord.document_id == doc_id)
        .order_by(AuditRecord.seq)).scalars().all()


def _delete_with_scan_step_patched_out(session, store, doc_id, monkeypatch):
    """Simulate a deletion from before this change: the key still goes, but
    the scan object is left in the store."""
    monkeypatch.setattr(deletion_scans, "plan", lambda *a, **kw: [])
    delete_document(session, doc_id, store, InMemoryIndex(), actor="t")
    session.commit()
    monkeypatch.undo()


def test_a_rerun_removes_a_leftover_scan_and_records_it_once(
        session, scanned_pdf, monkeypatch):
    store = originals()
    doc_id, scan_key, ocr_key = recover_document(session, store, scanned_pdf)
    _delete_with_scan_step_patched_out(session, store, doc_id, monkeypatch)

    assert store.objects.exists(scan_key)  # left behind, as before this change
    assert key_row(session, scan_key) is None  # the key went with the first deletion
    before = len(_records(session, doc_id))

    counts = delete_document(session, doc_id, store, InMemoryIndex(), actor="operator")
    session.commit()

    assert counts.original_scan == 1
    assert not store.objects.exists(scan_key)
    new = _records(session, doc_id)[before:]
    assert [(r.step, r.from_state, r.to_state) for r in new] == [
        ("remove-original-scan", "deleted", "deleted")]
    assert new[0].payload == {"actor": "operator", "original_scan": 1}
    assert verify_chain(session) == (True, None)

    again = delete_document(session, doc_id, store, InMemoryIndex(), actor="operator")
    session.commit()
    assert again.original_scan == 0
    assert len(_records(session, doc_id)) == before + 1  # nothing new appended


def test_each_leftover_kind_keeps_its_own_record_on_a_rerun(
        session, scanned_pdf, monkeypatch):
    store = originals()
    doc_id, scan_key, ocr_key = recover_document(session, store, scanned_pdf)
    _delete_with_scan_step_patched_out(session, store, doc_id, monkeypatch)
    assert store.objects.exists(scan_key)

    now = datetime.now(timezone.utc)
    session.add(DocumentKeyRecord(
        object_key=scan_key, document_id=doc_id, key_id="0123456789ab",
        kek_ref="wordsworth", wrapped_material=b"wrapped-left-behind",
        created_at=now, sealed_at=now))
    session.add(BoxMap(document_id=doc_id, boxmap_hash="h" * 64,
                       lists_hash=None, boxes=[]))
    store.objects.put(redacted_cache_key(doc_id, 1, "h" * 64), b"%PDF-1.4")
    session.commit()
    before = len(_records(session, doc_id))

    counts = delete_document(session, doc_id, store, InMemoryIndex(), actor="op")
    session.commit()

    new = _records(session, doc_id)[before:]
    assert [(r.step, r.from_state, r.to_state) for r in new] == [
        ("remove-renders", "deleted", "deleted"),
        ("remove-original-scan", "deleted", "deleted"),
        ("destroy-key", "deleted", "deleted"),
    ]
    assert new[0].payload == {"actor": "op", "renders_removed": 1,
                              "box_maps_removed": 1, "summaries_removed": 0}
    assert new[1].payload == {"actor": "op", "original_scan": 1}
    assert new[2].payload == {"actor": "op", "keys_destroyed": 1}
    assert counts.original_scan == 1 and counts.keys_destroyed == 1
    assert verify_chain(session) == (True, None)


def test_the_dry_run_over_an_old_deletion_reports_and_appends_nothing(
        session, scanned_pdf, monkeypatch):
    store = originals()
    doc_id, scan_key, ocr_key = recover_document(session, store, scanned_pdf)
    _delete_with_scan_step_patched_out(session, store, doc_id, monkeypatch)
    before = len(_records(session, doc_id))

    counts = delete_document(session, doc_id, store, InMemoryIndex(), actor="op",
                             dry_run=True)
    session.commit()

    assert counts.original_scan == 1
    assert store.objects.exists(scan_key)
    assert len(_records(session, doc_id)) == before
