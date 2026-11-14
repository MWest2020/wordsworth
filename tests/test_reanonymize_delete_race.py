# SPDX-License-Identifier: MIT
"""#463: a deletion racing `reanonymize` must not put the deleted document
back in the index.

`reanonymize` read the state without a lock and wrote the index entry, the
text and a `reanonymize` record (from == to, so no transition guard) after
that. A deletion that committed in between had already removed the entry and
the text; both came back, with `indexed -> indexed` after `deleted`. Now it
locks the row FOR SHARE before it reads the state, as `process` does (#462)."""
from __future__ import annotations

import threading
import time

from sqlalchemy import select, text

from race_setup import run, wait_for_a_lock_waiter
from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.audit import current_state, verify_chain
from wordsworth.deletion import delete_document
from wordsworth.models import AuditRecord, DocumentText
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import ingest, process, reanonymize
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State


def _bounded(session) -> None:
    session.execute(text("SET lock_timeout = '20s'"))


def _indexed(session_factory, store, index, pdf, embedder):
    with session_factory() as s:
        doc_id = ingest(s, store, pdf).id
        s.commit()
        assert process(s, doc_id, store, search_index=index,
                       embedder=embedder) == State.INDEXED
        s.commit()
    return doc_id


def _assert_deleted_last(session_factory, index, doc_id):
    assert not index.exists(str(doc_id))
    with session_factory() as s:
        assert current_state(s, doc_id) == State.DELETED
        assert s.get(DocumentText, doc_id) is None
        steps = s.execute(select(AuditRecord.step).where(
            AuditRecord.document_id == doc_id).order_by(AuditRecord.seq)
        ).scalars().all()
        assert steps[-1] == "delete"
        assert verify_chain(s) == (True, None)


class _PausingAnonymizer(DeterministicAnonymizer):
    """Holds inside `anonymize`: the state is read and the original fetched,
    nothing is written yet."""

    def __init__(self, paused, resume):
        self.paused, self.resume = paused, resume

    def anonymize(self, text):
        self.paused.set()
        assert self.resume.wait(30), "never resumed"
        return super().anonymize(text)


def _done_or_waiting(session_factory, thread, timeout=10.0) -> None:
    """Return once ``thread`` finished or some session waits on a lock."""
    deadline = time.monotonic() + timeout
    while thread.is_alive() and time.monotonic() < deadline:
        try:
            wait_for_a_lock_waiter(session_factory, timeout=0.2)
            return
        except AssertionError:
            pass
    assert time.monotonic() < deadline, "neither finished nor waited"


def test_a_deletion_during_reanonymize_stays_deleted(
        session_factory, born_digital_pii_pdf, fake_embedder):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doc_id = _indexed(session_factory, store, index, born_digital_pii_pdf,
                      fake_embedder)
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()

    def reanonymizing():
        with session_factory() as s:
            _bounded(s)
            result["state"] = reanonymize(
                s, doc_id, store, anonymizer=_PausingAnonymizer(paused, resume),
                search_index=index, embedder=fake_embedder)
            s.commit()

    def deleting():
        with session_factory() as s:
            _bounded(s)
            delete_document(s, doc_id, store, index, actor="t")
            s.commit()

    rean = run(errors, "reanonymize", reanonymizing)
    assert paused.wait(10)
    dele = run(errors, "delete", deleting)
    try:
        # Before the fix the deletion simply commits here; after it, it waits.
        _done_or_waiting(session_factory, dele)
    finally:
        resume.set()
        rean.join(30)
        dele.join(30)

    assert not errors, errors
    assert result["state"] == State.INDEXED
    _assert_deleted_last(session_factory, index, doc_id)


class _HoldingStore(InMemoryObjectStore):
    on_delete = None

    def delete(self, key):
        gone = super().delete(key)
        if self.on_delete is not None:
            self.on_delete()
        return gone


def test_reanonymize_waits_for_a_deletion_in_flight_and_stops(
        session_factory, born_digital_pdf, fake_embedder):
    store, index = _HoldingStore(), InMemoryIndex()
    doc_id = _indexed(session_factory, store, index, born_digital_pdf,
                      fake_embedder)
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()

    def hold():
        paused.set()
        assert resume.wait(30), "never resumed"

    def deleting():
        with session_factory() as s:
            _bounded(s)
            store.on_delete = hold  # row held, object gone, nothing committed
            delete_document(s, doc_id, store, index, actor="t")
            s.commit()

    def reanonymizing():
        with session_factory() as s:
            _bounded(s)
            result["state"] = reanonymize(s, doc_id, store, search_index=index,
                                          embedder=fake_embedder)
            s.commit()

    dele = run(errors, "delete", deleting)
    assert paused.wait(10)
    rean = run(errors, "reanonymize", reanonymizing)
    try:
        wait_for_a_lock_waiter(session_factory)
    finally:
        resume.set()
        dele.join(30)
        rean.join(30)

    # No error: it saw `deleted`, not a failed read of the removed object.
    assert not errors, errors
    assert result["state"] == State.DELETED
    _assert_deleted_last(session_factory, index, doc_id)


def test_normal_reanonymize_unaffected(session_factory, born_digital_pii_pdf,
                                       fake_embedder):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doc_id = _indexed(session_factory, store, index, born_digital_pii_pdf,
                      fake_embedder)
    with session_factory() as s:
        assert reanonymize(s, doc_id, store, search_index=index,
                           embedder=fake_embedder) == State.INDEXED
        s.commit()
        assert index.exists(str(doc_id))
        last = s.execute(select(AuditRecord.step).where(
            AuditRecord.document_id == doc_id).order_by(AuditRecord.seq.desc())
        ).scalars().first()
        assert last == "reanonymize"
        assert verify_chain(s) == (True, None)
    with session_factory() as s:
        s.execute(text("SET lock_timeout = '2s'"))  # the lock ended at commit
        delete_document(s, doc_id, store, index, actor="t")
        s.commit()
    _assert_deleted_last(session_factory, index, doc_id)
