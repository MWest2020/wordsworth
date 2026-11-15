# SPDX-License-Identifier: MIT
"""Row locks before the audit chain lock (`docs/reference/lock-order.md`):
#460 (dossier deletion), #466 (`release_deleted.release`, `dedupe`).

Each test holds a `documents` row in one session -- as a deletion, an ingest
or `process` does -- and starts the writer under test. The writer has to wait
for that row WITHOUT holding the chain lock: the holder then appends an audit
record, which needs the chain lock. A writer that took the chain lock first
makes that a deadlock (`DeadlockDetected` in one of the two)."""
from __future__ import annotations

from sqlalchemy import select, text

from race_setup import run, wait_for_a_lock_waiter
from wordsworth import audit, dossiers, release_deleted
from wordsworth.audit import current_state, verify_chain
from wordsworth.dedupe import run as dedupe_run
from wordsworth.deletion import released_object_key
from wordsworth.dossier_deletion import delete_dossier
from wordsworth.models import Document, DossierDocument
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import ingest, register, transition
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State


def _bounded(session) -> None:
    session.execute(text("SET lock_timeout = '20s'"))


def _hold_row_then_append(session_factory, doc_id, errors, start_writer):
    """Hold ``doc_id``'s row, start the writer, wait until it waits, append
    for that document (the chain lock), commit. Returns the joined writer."""
    with session_factory() as holder:
        _bounded(holder)
        holder.execute(select(Document.id).where(Document.id == doc_id)
                       .with_for_update(key_share=True))  # FOR NO KEY UPDATE
        writer = start_writer()
        try:
            wait_for_a_lock_waiter(session_factory)
            state = current_state(holder, doc_id).value
            audit.append(holder, document_id=doc_id, from_state=state,
                         to_state=state, step="held-by-test")
            holder.commit()
        except Exception as exc:  # the deadlock's victim may be this side
            errors["holder"] = exc
            holder.rollback()
        writer.join(30)
    assert not writer.is_alive()


def test_dossier_deletion_waits_for_a_later_member_without_the_chain_lock(
        session_factory):
    """#460, as the issue asks: two members, a second session holding the
    later member's row and then appending."""
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        for pdf in (b"%PDF-1.4 a", b"%PDF-1.4 b"):
            ingest(s, store, pdf, dossier="zaak")
        dossier_id = dossiers.ensure(s, "zaak").id
        s.commit()
        order = s.execute(select(DossierDocument.document_id).where(
            DossierDocument.dossier_id == dossier_id)).scalars().all()
    errors = {}

    def deleting_dossier():
        with session_factory() as s:
            _bounded(s)
            delete_dossier(s, dossier_id, store, index, actor="t")
            s.commit()

    _hold_row_then_append(session_factory, order[-1], errors,
                          lambda: run(errors, "delete-dossier", deleting_dossier))
    assert not errors, errors
    with session_factory() as s:
        assert [current_state(s, d) for d in order] == [State.DELETED] * 2
        assert verify_chain(s) == (True, None)


def test_release_waits_for_the_row_without_the_chain_lock(session_factory):
    """#466 (2): `release` appended (chain lock) before its row UPDATE was
    flushed, so a rerun of `delete_document` holding the row deadlocked it."""
    key = "documents/" + "cd" * 32
    with session_factory() as s:
        doc_id = register(s, key).id
        transition(s, doc_id, State.DELETED, step="delete")  # before the release
        s.commit()
    errors = {}

    def releasing():
        with session_factory() as s:
            _bounded(s)
            release_deleted.release(s, doc_id, key)
            s.commit()

    _hold_row_then_append(session_factory, doc_id, errors,
                          lambda: run(errors, "release", releasing))
    assert not errors, errors
    with session_factory() as s:
        assert s.get(Document, doc_id).object_key == released_object_key(doc_id)
        assert verify_chain(s) == (True, None)


def test_release_skips_a_key_released_while_it_waited(session_factory):
    """Read again under the lock: a document whose key was released in
    between gets no second `release-key` record."""
    key = "documents/" + "ef" * 32
    with session_factory() as s:
        doc_id = register(s, key).id
        transition(s, doc_id, State.DELETED, step="delete")
        s.commit()
        assert release_deleted.release(s, doc_id, key) is True
        s.commit()
        assert release_deleted.release(s, doc_id, key) is False
        s.commit()
    report = release_deleted.run(session_factory, apply=True)
    assert report["released"] == []


def test_dedupe_locks_every_copy_before_its_first_record(legacy_copies,
                                                         session_factory):
    """#466 (3): three rows of one object; the copy retired LAST is held.
    Dedupe locked it only after the first copy's records took the chain."""
    index = InMemoryIndex()
    key = "documents/" + "x" * 64
    with session_factory() as s:
        ids = []
        for _ in range(3):
            doc = register(s, key)
            s.flush()
            ids.append(doc.id)
        s.commit()
    errors, report = {}, {}

    def deduping():
        report.update(dedupe_run(session_factory, index, apply=True,
                                 expect={"copies": 2, "memberships": 0}))

    _hold_row_then_append(session_factory, ids[-1], errors,
                          lambda: run(errors, "dedupe", deduping))
    assert not errors, errors
    assert report["done"]["superseded"] == 2
    with session_factory() as s:
        assert all(s.get(Document, c).superseded_by == ids[0] for c in ids[1:])
        assert verify_chain(s) == (True, None)
