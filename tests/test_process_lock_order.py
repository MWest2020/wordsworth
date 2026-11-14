# SPDX-License-Identifier: MIT
"""#462: the FOR SHARE lock `process` takes on the document row adds no
deadlock with an audit append, a deletion, or a dossier deletion (nor does
the one `ingest` takes since #452).

The order is every document writer's: the row first, the audit chain's
advisory lock after. An audit append takes the chain lock and then only KEY
SHARE on the row (the foreign key), which FOR SHARE does not block. A dossier
deletion deletes several documents in one transaction, so after the first
`deleted` record it holds the chain lock; it therefore locks every member's
row before its first append, or it would wait for a `process` that waits
for it."""
from __future__ import annotations

import threading

from sqlalchemy import select, text

from race_setup import SpyOriginalsStore, pause_process, run, wait_for_a_lock_waiter
from wordsworth import audit, dossiers
from wordsworth.audit import current_state, verify_chain
from wordsworth.deletion import delete_document
from wordsworth.dossier_deletion import delete_dossier
from wordsworth.models import DossierDocument
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


def test_a_dossier_deletion_does_not_deadlock_with_process(
        session_factory, born_digital_pdf, born_digital_pii_pdf, fake_embedder,
        monkeypatch):
    """`process` of the member deleted second holds its row, not yet the
    chain. Before the dossier deletion locked its members up front, it
    deleted the first (taking the chain lock), then waited for that row
    while `process` waited for the chain: a deadlock."""
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        a = ingest(s, store, born_digital_pii_pdf, dossier="zaak").id
        b = ingest(s, store, born_digital_pdf, dossier="zaak").id
        dossier_id = dossiers.ensure(s, "zaak").id
        s.commit()
        # The member `delete_dossier` reaches last is the one being processed.
        order = s.execute(select(DossierDocument.document_id).where(
            DossierDocument.dossier_id == dossier_id)).scalars().all()
    first, last = order[0], order[-1]
    assert {first, last} == {a, b}
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()
    pause_process(monkeypatch, "profile", paused, resume)

    def deleting_dossier():
        with session_factory() as s:
            _bounded(s)
            delete_dossier(s, dossier_id, store, index, actor="t")
            s.commit()

    proc = run(errors, "process",
               _processing(session_factory, store, index, fake_embedder,
                           last, result))
    assert paused.wait(10)  # the row is held; no audit record yet
    dele = run(errors, "delete-dossier", deleting_dossier)
    try:
        wait_for_a_lock_waiter(session_factory)
    finally:
        resume.set()
        proc.join(30)
        dele.join(30)

    assert not errors, errors
    assert result["state"] == State.INDEXED
    assert not index.exists(str(last))
    with session_factory() as s:
        assert current_state(s, first) == State.DELETED
        assert current_state(s, last) == State.DELETED
        assert verify_chain(s) == (True, None)


def test_a_dossier_deletion_does_not_deadlock_with_an_ingest(session_factory):
    """The same cycle with `ingest` (#452's FOR SHARE, then the membership
    record): the same bytes delivered into another dossier while this one
    is deleted. Locked up front, the deletion waits, then finds the document
    held elsewhere and only releases it."""
    store, index = SpyOriginalsStore(), InMemoryIndex()
    data = {b"%PDF-1.4 a": None, b"%PDF-1.4 b": None}
    with session_factory() as s:
        for pdf in data:
            data[pdf] = ingest(s, store, pdf, dossier="zaak").id
        dossier_id = dossiers.ensure(s, "zaak").id
        s.commit()
        order = s.execute(select(DossierDocument.document_id).where(
            DossierDocument.dossier_id == dossier_id)).scalars().all()
    first, last = order[0], order[-1]
    last_pdf = next(pdf for pdf, doc_id in data.items() if doc_id == last)
    errors, paused, resume = {}, threading.Event(), threading.Event()

    def hold():
        paused.set()
        assert resume.wait(30), "never resumed"

    def ingesting():
        with session_factory() as s:
            _bounded(s)
            store.on_put = hold  # past `lock_live`: the row is held
            assert ingest(s, store, last_pdf, dossier="ander").id == last
            s.commit()

    def deleting_dossier():
        with session_factory() as s:
            _bounded(s)
            delete_dossier(s, dossier_id, store, index, actor="t")
            s.commit()

    ing = run(errors, "ingest", ingesting)
    assert paused.wait(10)
    dele = run(errors, "delete-dossier", deleting_dossier)
    try:
        wait_for_a_lock_waiter(session_factory)
    finally:
        resume.set()
        ing.join(30)
        dele.join(30)

    assert not errors, errors
    with session_factory() as s:
        assert current_state(s, first) == State.DELETED
        assert current_state(s, last) == State.REGISTERED
        assert verify_chain(s) == (True, None)
