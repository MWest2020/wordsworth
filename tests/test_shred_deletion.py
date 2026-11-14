# SPDX-License-Identifier: MIT
"""`originals-crypto-shred` task 2: deleting a document destroys the data key
of its sealed object(s) in the same transaction, as a hard-error step."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from shred_setup import KEY, PDF, key_row, opens_from_backup, originals, sealed
from wordsworth import deletion_keys
from wordsworth.audit import current_state
from wordsworth.deletion import delete_document
from wordsworth.document_keys import OriginalsKeyUnavailable
from wordsworth.models import AuditRecord, DocumentText
from wordsworth.ocr import FixedOcrEngine
from wordsworth.pipeline import ingest, process, register
from wordsworth.recovery import recover
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State


def _records(session, doc_id, step=None):
    q = select(AuditRecord).where(AuditRecord.document_id == doc_id)
    if step:
        q = q.where(AuditRecord.step == step)
    return session.execute(q.order_by(AuditRecord.seq)).scalars().all()


def test_without_keys_the_row_goes_and_a_backup_copy_cannot_be_opened(session):
    store, index = originals(), InMemoryIndex()
    doc_id = sealed(session, store)
    session.commit()
    backup = {KEY: store.objects.get_raw(KEY)}  # a backup taken BEFORE
    assert opens_from_backup(session, backup) == PDF

    counts = delete_document(session, doc_id, store, index, actor="t")
    session.commit()

    assert counts.keys_destroyed == 1
    assert key_row(session) is None
    assert not store.objects.exists(KEY)
    with pytest.raises(OriginalsKeyUnavailable):
        opens_from_backup(session, backup)


def test_with_keys_the_entry_leaves_that_cache(session):
    store, index = originals(), InMemoryIndex()
    doc_id = sealed(session, store)
    session.commit()
    store.get_original(session, KEY)
    assert KEY in store.keys._cache

    delete_document(session, doc_id, store, index, actor="t", keys=store.keys)
    session.commit()

    assert KEY not in store.keys._cache
    assert key_row(session) is None


def test_doomed_runs_before_the_index_entry_and_the_object_go(session, monkeypatch):
    store, index = originals(), InMemoryIndex()
    doc_id = sealed(session, store)
    index.index(str(doc_id), "tekst", KEY)
    session.commit()

    def refuse(*a, **kw):
        raise RuntimeError("doomed refused")
    monkeypatch.setattr(deletion_keys, "doomed", refuse)
    with pytest.raises(RuntimeError):
        delete_document(session, doc_id, store, index, actor="t")
    session.rollback()

    assert index.exists(str(doc_id))
    assert store.objects.exists(KEY)
    assert key_row(session) is not None


def test_an_ocr_recovered_document_loses_both_keys(session, scanned_pdf):
    store, index = originals(), InMemoryIndex()
    doc = ingest(session, store, scanned_pdf)
    session.commit()
    scan_key = doc.object_key
    assert process(session, doc.id, store) == State.UNPROCESSABLE_OCR
    session.commit()
    recover(session, doc.id, store, threshold=10,
            engine=FixedOcrEngine("Herstelde tekst van een gescand stuk. " * 3))
    session.commit()
    ocr_key = doc.object_key
    assert ocr_key != scan_key
    assert key_row(session, scan_key) and key_row(session, ocr_key)

    counts = delete_document(session, doc.id, store, index, actor="t")
    session.commit()

    assert counts.keys_destroyed == 2
    assert key_row(session, scan_key) is None
    assert key_row(session, ocr_key) is None
    rec = _records(session, doc.id, "delete")[0]
    assert rec.payload["keys_destroyed"] == 2


def test_a_failure_destroying_the_key_is_a_hard_error_and_a_rerun_finishes(
        session, monkeypatch):
    store, index = originals(), InMemoryIndex()
    doc_id = sealed(session, store)
    session.commit()

    def broken(*a, **kw):
        raise RuntimeError("key row delete failed")
    monkeypatch.setattr(deletion_keys, "destroy", broken)
    with pytest.raises(RuntimeError):
        delete_document(session, doc_id, store, index, actor="t")
    session.rollback()
    assert current_state(session, doc_id) != State.DELETED
    assert _records(session, doc_id, "delete") == []
    assert key_row(session) is not None

    monkeypatch.undo()
    counts = delete_document(session, doc_id, store, index, actor="t")
    session.commit()
    assert current_state(session, doc_id) == State.DELETED
    assert counts.keys_destroyed == 1
    assert key_row(session) is None


def test_a_legacy_plaintext_original_deletes_as_before(session):
    store, index = originals(), InMemoryIndex()
    doc = register(session, KEY)
    store.objects.put(KEY, b"%PDF-1.4 legacy plaintext, never sealed")
    session.add(DocumentText(document_id=doc.id, anonymized_text="tekst"))
    session.commit()

    counts = delete_document(session, doc.id, store, index, actor="t")
    session.commit()

    assert current_state(session, doc.id) == State.DELETED
    assert counts.keys_destroyed == 0 and counts.object == 1 and counts.text == 1
    assert _records(session, doc.id, "delete")[0].payload["keys_destroyed"] == 0
