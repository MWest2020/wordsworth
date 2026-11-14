# SPDX-License-Identifier: MIT
"""#452: the FOR SHARE lock `ingest` takes on the document row, and the
FOR NO KEY UPDATE a deletion now takes first, add no deadlock with an audit
append.

An audit append takes the chain's advisory lock and then a KEY SHARE lock on
the document row (the foreign key). KEY SHARE and FOR SHARE are compatible, so
an ingest holding the row is never waited on by an append, and an append
holding the chain lock only makes the ingest wait for it at its own append
(the dossier membership record), never the other way round."""
from __future__ import annotations

import threading

from sqlalchemy import text

from race_setup import PDF, SpyOriginalsStore, run, wait_for_a_lock_waiter
from wordsworth import audit
from wordsworth.audit import current_state, verify_chain
from wordsworth.deletion import delete_document
from wordsworth.models import DossierDocument
from wordsworth.pipeline import ingest
from wordsworth.search_index import InMemoryIndex


def _append(session, doc_id) -> None:
    state = current_state(session, doc_id).value
    audit.append(session, document_id=doc_id, from_state=state, to_state=state,
                 step="detection_feedback", payload={"actor": "other"})


def _registered(session_factory, store):
    with session_factory() as s:
        doc_id = ingest(s, store, PDF).id
        s.commit()
    return doc_id


def _bounded(session) -> None:
    # A wait that never ends fails the test instead of hanging it.
    session.execute(text("SET lock_timeout = '20s'"))


def test_an_append_waits_for_an_ingest_holding_the_row(session_factory):
    store = SpyOriginalsStore()
    doc_id = _registered(session_factory, store)
    errors, appended = {}, threading.Event()

    def append():
        with session_factory() as s:
            _bounded(s)
            _append(s, doc_id)
            s.commit()
        appended.set()

    with session_factory() as ingesting:
        _bounded(ingesting)
        # Holds FOR SHARE on the row and, through the membership record,
        # the chain lock.
        ingest(ingesting, store, PDF, dossier="zaak")
        worker = run(errors, "append", append)
        wait_for_a_lock_waiter(session_factory)
        ingesting.commit()
    worker.join(30)

    assert not errors, errors
    assert appended.is_set()
    with session_factory() as s:
        assert verify_chain(s) == (True, None)


def test_an_ingest_takes_the_row_while_an_append_holds_the_chain(session_factory):
    store = SpyOriginalsStore()
    doc_id = _registered(session_factory, store)
    errors, locked = {}, threading.Event()

    store.on_put = locked.set  # past `lock_live`: FOR SHARE was granted

    def ingest_into_dossier():
        with session_factory() as s:
            _bounded(s)
            ingest(s, store, PDF, dossier="zaak")
            s.commit()

    with session_factory() as appending:
        _bounded(appending)
        _append(appending, doc_id)  # chain lock + KEY SHARE on the row
        worker = run(errors, "ingest", ingest_into_dossier)
        # The row lock is granted while the append holds KEY SHARE on it ...
        assert locked.wait(10)
        # ... and the ingest then waits only for the chain lock.
        wait_for_a_lock_waiter(session_factory)
        appending.commit()
    worker.join(30)

    assert not errors, errors
    with session_factory() as s:
        assert s.get(DossierDocument, (s.execute(text(
            "SELECT id FROM dossiers")).scalar_one(), doc_id)) is not None
        assert verify_chain(s) == (True, None)


def test_an_append_commits_while_a_deletion_holds_the_row(session_factory):
    store = SpyOriginalsStore()
    doc_id = _registered(session_factory, store)
    errors, paused, resume = {}, threading.Event(), threading.Event()

    def hold(key):
        paused.set()
        assert resume.wait(30), "never resumed"

    def delete():
        with session_factory() as s:
            _bounded(s)
            store.on_delete = hold  # row locked, object gone, no append yet
            delete_document(s, doc_id, store, InMemoryIndex(), actor="t")
            s.commit()

    deleting = run(errors, "delete", delete)
    assert paused.wait(10)
    try:
        with session_factory() as s:
            _bounded(s)
            _append(s, doc_id)  # KEY SHARE: not blocked by NO KEY UPDATE
            s.commit()
    finally:
        resume.set()
        deleting.join(30)

    assert not errors, errors
    with session_factory() as s:
        assert verify_chain(s) == (True, None)
