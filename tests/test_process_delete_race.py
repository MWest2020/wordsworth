# SPDX-License-Identifier: MIT
"""#462: a deletion during `process` must not leave the document's anonymized
text in the index.

`process` runs as one transaction and, before the fix, took no lock on the
document row. A deletion that started while it ran found no index entry yet
(and no committed text), then waited only for the audit chain lock `process`
held since its first record; `process` wrote the index entry and committed,
and the deletion then recorded `deleted` over an indexed document with its
text still stored. Now `process` locks the row FOR SHARE first, so the
deletion waits before it looks at anything and removes what `process` wrote;
a deletion already holding the row makes `process` wait and then stop."""
from __future__ import annotations

import threading

from sqlalchemy import select, text

from race_setup import pause_process, run, wait_for_a_lock_waiter
from wordsworth.audit import current_state, verify_chain
from wordsworth.deletion import delete_document
from wordsworth.models import AuditRecord, DocumentText
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import ingest, process
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State


def _bounded(session) -> None:
    session.execute(text("SET lock_timeout = '20s'"))


def _ingested(session_factory, store, pdf):
    with session_factory() as s:
        doc_id = ingest(s, store, pdf).id
        s.commit()
    return doc_id


def _assert_gone(session_factory, index, doc_id):
    """Deleted, and nothing `process` wrote survived the deletion."""
    assert not index.exists(str(doc_id))
    with session_factory() as s:
        assert current_state(s, doc_id) == State.DELETED
        assert s.get(DocumentText, doc_id) is None
        records = s.execute(select(AuditRecord).where(
            AuditRecord.document_id == doc_id).order_by(AuditRecord.seq)
        ).scalars().all()
        # The `deleted` record extends the state the document really had.
        assert records[-1].step == "delete"
        assert records[-1].from_state == records[-2].to_state
        assert verify_chain(s) == (True, None)


def test_a_deletion_during_process_removes_what_process_indexed(
        session_factory, born_digital_pdf, fake_embedder, monkeypatch):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doc_id = _ingested(session_factory, store, born_digital_pdf)
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()
    pause_process(monkeypatch, "anonymized", paused, resume)

    def processing():
        with session_factory() as s:
            _bounded(s)
            result["state"] = process(s, doc_id, store, search_index=index,
                                      embedder=fake_embedder)
            s.commit()

    def deleting():
        with session_factory() as s:
            _bounded(s)
            delete_document(s, doc_id, store, index, actor="t")
            s.commit()

    proc = run(errors, "process", processing)
    assert paused.wait(10)  # ANONYMIZED written; the chain lock is held
    dele = run(errors, "delete", deleting)
    try:
        wait_for_a_lock_waiter(session_factory)
    finally:
        resume.set()
        proc.join(30)
        dele.join(30)

    assert not errors, errors
    assert result["state"] == State.INDEXED
    _assert_gone(session_factory, index, doc_id)


class _HoldingStore(InMemoryObjectStore):
    """Runs ``on_delete`` after a delete: the deletion has the row, and the
    object is gone, but nothing is committed yet."""

    on_delete = None

    def delete(self, key):
        gone = super().delete(key)
        if self.on_delete is not None:
            self.on_delete()
        return gone


def test_process_waits_for_a_deletion_in_flight_and_stops(
        session_factory, born_digital_pdf, fake_embedder):
    store, index = _HoldingStore(), InMemoryIndex()
    doc_id = _ingested(session_factory, store, born_digital_pdf)
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()

    def hold():
        paused.set()
        assert resume.wait(30), "never resumed"

    def deleting():
        with session_factory() as s:
            _bounded(s)
            store.on_delete = hold
            delete_document(s, doc_id, store, index, actor="t")
            s.commit()

    def processing():
        with session_factory() as s:
            _bounded(s)
            result["state"] = process(s, doc_id, store, search_index=index,
                                      embedder=fake_embedder)
            s.commit()

    dele = run(errors, "delete", deleting)
    assert paused.wait(10)
    proc = run(errors, "process", processing)
    try:
        wait_for_a_lock_waiter(session_factory)
    finally:
        resume.set()
        dele.join(30)
        proc.join(30)

    # No error: it saw the deletion and did nothing, not a failed read of
    # the object the deletion removed.
    assert not errors, errors
    assert result["state"] == State.DELETED
    with session_factory() as s:
        steps = s.execute(select(AuditRecord.step).where(
            AuditRecord.document_id == doc_id).order_by(AuditRecord.seq)
        ).scalars().all()
        assert steps == ["register", "delete"]
        assert verify_chain(s) == (True, None)
    assert not index.exists(str(doc_id))


def test_process_of_a_deleted_document_does_nothing(
        session_factory, born_digital_pdf, fake_embedder):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doc_id = _ingested(session_factory, store, born_digital_pdf)
    with session_factory() as s:
        delete_document(s, doc_id, store, index, actor="t")
        s.commit()
    with session_factory() as s:
        assert process(s, doc_id, store, search_index=index,
                       embedder=fake_embedder) == State.DELETED
        s.commit()
        assert verify_chain(s) == (True, None)
    assert not index.exists(str(doc_id))


def test_normal_processing_then_deletion(session_factory, born_digital_pdf,
                                         fake_embedder):
    """Unaffected: `process` indexes as before, and its row lock ends with
    its commit -- a deletion right after does not wait."""
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doc_id = _ingested(session_factory, store, born_digital_pdf)
    with session_factory() as s:
        assert process(s, doc_id, store, search_index=index,
                       embedder=fake_embedder) == State.INDEXED
        s.commit()
        assert index.exists(str(doc_id))
        assert s.get(DocumentText, doc_id) is not None
    with session_factory() as s:
        s.execute(text("SET lock_timeout = '2s'"))
        delete_document(s, doc_id, store, index, actor="t")
        s.commit()
    _assert_gone(session_factory, index, doc_id)
