# SPDX-License-Identifier: MIT
"""#462: a dossier deletion adds no deadlock with `process`, `ingest` (#452)
or a deletion of a member's copy.

It deletes several members in one transaction, so after the first `deleted`
record it holds the audit chain lock. It therefore locks every member's row
and its copies' rows before its first append (`dossier_locks`); otherwise it
waits for a row whose holder waits for the chain lock. Which rows, and that
a dry run locks none: `test_dossier_deletion_lock_set.py`."""
from __future__ import annotations

import threading
import uuid

from sqlalchemy import select, text

from race_setup import SpyOriginalsStore, pause_process, run, wait_for_a_lock_waiter
from wordsworth import dossier_deletion, dossiers
from wordsworth.audit import current_state, verify_chain
from wordsworth.deletion import delete_document
from wordsworth.dossier_deletion import delete_dossier
from wordsworth.models import Document, DossierDocument
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import ingest, process, register, transition
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State


def _bounded(session) -> None:
    # A wait that never ends fails the test instead of hanging it.
    session.execute(text("SET lock_timeout = '20s'"))


def _processing(session_factory, store, index, embedder, doc_id, result):
    def go():
        with session_factory() as s:
            _bounded(s)
            result["state"] = process(s, doc_id, store, search_index=index,
                                      embedder=embedder)
            s.commit()
    return go


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


def test_a_dossier_deletion_does_not_deadlock_with_deleting_a_copy(
        session_factory, monkeypatch):
    """A superseded copy of a member, with a lower id than the member. The
    dossier deletion holds the copy's row from its pre-lock, so deleting the
    copy waits for it. With the member alone locked, crypto-shred's `doomed`
    (copy, then member, by id) deadlocked against it (#464 review)."""
    store, index = InMemoryObjectStore(), InMemoryIndex()
    key = "documents/" + "ab" * 32
    store.put(key, b"%PDF-1.4 x")
    copy = uuid.UUID(int=1)
    with session_factory() as s:
        member = register(s, key).id
        s.add(Document(id=copy, object_key=key, superseded_by=member))
        s.flush()
        transition(s, copy, State.REGISTERED, step="register")
        transition(s, copy, State.SUPERSEDED, step="supersede")
        dossier_id = dossiers.ensure(s, "zaak").id
        dossiers.add(s, dossier_id, member, actor="t")
        s.commit()
    assert copy < member
    errors, paused, resume = {}, threading.Event(), threading.Event()
    real = dossier_deletion.delete_document

    def held(*args, **kwargs):  # past the pre-lock, before any append
        paused.set()
        assert resume.wait(30), "never resumed"
        return real(*args, **kwargs)
    monkeypatch.setattr(dossier_deletion, "delete_document", held)

    def deleting_dossier():
        with session_factory() as s:
            _bounded(s)
            delete_dossier(s, dossier_id, store, index, actor="t")
            s.commit()

    def deleting_copy():
        with session_factory() as s:
            _bounded(s)
            delete_document(s, copy, store, index, actor="t")
            s.commit()

    dele = run(errors, "delete-dossier", deleting_dossier)
    assert paused.wait(10)
    cop = run(errors, "delete-copy", deleting_copy)
    try:
        wait_for_a_lock_waiter(session_factory)  # the copy's row is held
    finally:
        resume.set()
        dele.join(30)
        cop.join(30)

    assert not errors, errors
    with session_factory() as s:
        assert current_state(s, member) == State.DELETED
        assert current_state(s, copy) == State.DELETED
        assert verify_chain(s) == (True, None)
