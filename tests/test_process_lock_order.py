# SPDX-License-Identifier: MIT
"""#462: the FOR SHARE lock `process` takes on the document row adds no
deadlock with an audit append or a deletion. The dossier deletion's side is
in `test_dossier_deletion_deadlocks.py`.

The order is every document writer's: the row first, the audit chain's
advisory lock after. An audit append takes the chain lock and then only KEY
SHARE on the row (the foreign key), which FOR SHARE does not block.
"""
from __future__ import annotations

import threading

from sqlalchemy import text

from race_setup import pause_process, run, wait_for_a_lock_waiter
from wordsworth import audit
from wordsworth.audit import current_state, verify_chain
from wordsworth.deletion import delete_document
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import ingest, process
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State


def _bounded(session) -> None:
    # A wait that never ends fails the test instead of hanging it.
    session.execute(text("SET lock_timeout = '20s'"))


def _append(session, doc_id) -> None:
    state = current_state(session, doc_id).value
    audit.append(session, document_id=doc_id, from_state=state, to_state=state,
                 step="detection_feedback", payload={"actor": "other"})


def _processing(session_factory, store, index, embedder, doc_id, result):
    def go():
        with session_factory() as s:
            _bounded(s)
            result["state"] = process(s, doc_id, store, search_index=index,
                                      embedder=embedder)
            s.commit()
    return go


def test_an_append_waits_only_for_the_chain_while_process_holds_the_row(
        session_factory, born_digital_pdf, fake_embedder, monkeypatch):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        doc_id = ingest(s, store, born_digital_pdf).id
        s.commit()
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()
    pause_process(monkeypatch, "anonymized", paused, resume)

    def appending():
        with session_factory() as s:
            _bounded(s)
            _append(s, doc_id)
            s.commit()

    proc = run(errors, "process",
               _processing(session_factory, store, index, fake_embedder,
                           doc_id, result))
    assert paused.wait(10)
    app = run(errors, "append", appending)
    try:
        wait_for_a_lock_waiter(session_factory)
    finally:
        resume.set()
        proc.join(30)
        app.join(30)

    assert not errors, errors
    assert result["state"] == State.INDEXED
    with session_factory() as s:
        assert verify_chain(s) == (True, None)


def test_process_deletion_and_an_append_all_finish(
        session_factory, born_digital_pdf, fake_embedder, monkeypatch):
    """`process` holds the row and the chain; the deletion waits for the
    row, the append for the chain. Released, all three commit."""
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        doc_id = ingest(s, store, born_digital_pdf).id
        s.commit()
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()
    pause_process(monkeypatch, "anonymized", paused, resume)

    def deleting():
        with session_factory() as s:
            _bounded(s)
            delete_document(s, doc_id, store, index, actor="t")
            s.commit()

    def appending():
        with session_factory() as s:
            _bounded(s)
            _append(s, doc_id)
            s.commit()

    proc = run(errors, "process",
               _processing(session_factory, store, index, fake_embedder,
                           doc_id, result))
    assert paused.wait(10)
    dele = run(errors, "delete", deleting)
    app = run(errors, "append", appending)
    try:
        wait_for_a_lock_waiter(session_factory)
    finally:
        resume.set()
        for t in (proc, dele, app):
            t.join(30)

    assert not errors, errors
    assert result["state"] == State.INDEXED
    assert not index.exists(str(doc_id))
    with session_factory() as s:
        assert current_state(s, doc_id) == State.DELETED
        assert verify_chain(s) == (True, None)
