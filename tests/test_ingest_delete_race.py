# SPDX-License-Identifier: MIT
"""#452: an ingest racing a deletion must not bring the deleted original back.

`register_live` reads without a lock. Before the fix, a deletion that
committed between it and `write_original` left the ingest writing the object
for the deleted document again (on main: resealed under its old key row;
with crypto-shred: under a freshly minted one). Now `ingest` locks the row FOR
SHARE and re-checks; a document no longer live is looked up again, and the
bytes of a deleted document ingested again are a new document
(document-deletion, "The same bytes can be ingested again")."""
from __future__ import annotations

import hashlib
import threading

import pytest
from sqlalchemy import select

from race_setup import PDF, SpyOriginalsStore, key_rows_for, run, wait_for_a_lock_waiter
from wordsworth import pipeline as pipeline_mod
from wordsworth.audit import current_state
from wordsworth.deletion import delete_document, released_object_key
from wordsworth.models import AuditRecord, Document
from wordsworth.originals_io import read_original
from wordsworth.pipeline import IngestRaceError, ingest
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

KEY = "documents/" + hashlib.sha256(PDF).hexdigest()


def _ingested(session_factory, store) -> object:
    with session_factory() as s:
        doc_id = ingest(s, store, PDF).id
        s.commit()
    store.put_for.clear()
    return doc_id


def _delete(session_factory, store, doc_id) -> None:
    with session_factory() as s:
        delete_document(s, doc_id, store, InMemoryIndex(), actor="t")
        s.commit()


def _assert_deleted_stays_deleted(session_factory, store, old_id, rows_before):
    """The deleted document got no write and no key row; the bytes, if
    written, belong to a new live document."""
    assert old_id not in store.put_for
    with session_factory() as s:
        old = s.get(Document, old_id)
        assert current_state(s, old_id) == State.DELETED
        assert old.object_key == released_object_key(old_id)
        last = s.execute(select(AuditRecord.step).where(
            AuditRecord.document_id == old_id).order_by(AuditRecord.seq.desc())
        ).scalars().first()
        assert last == "delete"
        # No row minted for it: what remains is at most the row it already had
        # (main keeps it; crypto-shred destroys it).
        assert key_rows_for(s, old_id) <= rows_before
        new = pipeline_mod.live_document_for(s, KEY)
        assert new is not None and new.id != old_id
        assert store.put_for == [new.id]
        assert read_original(s, store, KEY) == PDF


def test_deletion_committed_between_register_live_and_write(
        session_factory, monkeypatch):
    store = SpyOriginalsStore()
    old_id = _ingested(session_factory, store)
    with session_factory() as s:
        rows_before = key_rows_for(s, old_id)
    real, calls = pipeline_mod.register_live, []

    def register_then_delete(session, *args, **kwargs):
        doc = real(session, *args, **kwargs)
        calls.append(doc.id)
        if len(calls) == 1:
            assert doc.id == old_id  # found the live document, unlocked
            _delete(session_factory, store, old_id)  # second session commits
        return doc

    monkeypatch.setattr(pipeline_mod, "register_live", register_then_delete)
    with session_factory() as s:
        new_id = ingest(s, store, PDF).id
        s.commit()

    _assert_deleted_stays_deleted(session_factory, store, old_id, rows_before)
    assert calls == [old_id, new_id]  # looked up again once, after the lock


@pytest.mark.parametrize("pause", ["after removing the object", "before committing"])
def test_ingest_waits_for_a_deletion_in_flight(session_factory, pause):
    """The deletion holds the row from its start; the ingest blocks on FOR
    SHARE until it commits, then sees the document deleted and registers a
    new one -- also when the object is already gone but the deletion has not
    reached its own update of the row yet."""
    store = SpyOriginalsStore()
    old_id = _ingested(session_factory, store)
    with session_factory() as s:
        rows_before = key_rows_for(s, old_id)
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()

    def hold():
        paused.set()
        assert resume.wait(30), "never resumed"

    def delete():
        with session_factory() as s:
            if pause == "after removing the object":
                store.on_delete = lambda key: hold() if key == KEY else None
            delete_document(s, old_id, store, InMemoryIndex(), actor="t")
            s.flush()
            if pause == "before committing":
                hold()
            s.commit()

    def ingest_again():
        with session_factory() as s:
            # Into a dossier: the membership record takes the chain lock too.
            result["id"] = ingest(s, store, PDF, dossier="zaak").id
            s.commit()

    deleting = run(errors, "delete", delete)
    assert paused.wait(10)
    ingesting = run(errors, "ingest", ingest_again)
    try:
        wait_for_a_lock_waiter(session_factory)
        assert store.put_for == []  # nothing written while the row is held
    finally:
        resume.set()
        deleting.join(30)
        ingesting.join(30)

    assert not errors, errors
    assert result["id"] != old_id
    _assert_deleted_stays_deleted(session_factory, store, old_id, rows_before)


def test_normal_ingest_and_reingest_still_work(session_factory):
    store = SpyOriginalsStore()
    with session_factory() as s:
        first = ingest(s, store, PDF, dossier="zaak-1")
        s.commit()
        again = ingest(s, store, PDF, dossier="zaak-2")
        s.commit()
        assert again.id == first.id
        assert store.put_for == [first.id, first.id]
        assert key_rows_for(s, first.id)
        assert read_original(s, store, KEY) == PDF
        assert current_state(s, first.id) == State.REGISTERED


def test_a_deleted_document_still_holding_its_key_is_refused(session_factory):
    """Deleted before deletions released the key (release-deleted-keys
    exists for these): it is still found by key, never written again."""
    store = SpyOriginalsStore()
    old_id = _ingested(session_factory, store)
    _delete(session_factory, store, old_id)
    with session_factory() as s:
        s.get(Document, old_id).object_key = KEY  # as before the release
        s.commit()

    with session_factory() as s:
        with pytest.raises(IngestRaceError, match="release-deleted-keys"):
            ingest(s, store, PDF)
        s.rollback()
    assert store.put_for == []
    assert not store.objects.exists(KEY)
