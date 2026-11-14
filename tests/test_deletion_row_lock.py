# SPDX-License-Identifier: MIT
"""#452 review: the row lock `delete_document` takes before it removes
anything -- taken only by a real deletion, never by a dry run, and followed by
a fresh read of the row, so a deletion that waited for another one sees the
key that one released, not the one it read before waiting."""
from __future__ import annotations

import hashlib

from sqlalchemy import select, text

from race_setup import PDF, SpyOriginalsStore, run, wait_for_a_lock_waiter
from wordsworth.deletion import delete_document, released_object_key
from wordsworth.models import AuditRecord, Document
from wordsworth.pipeline import ingest
from wordsworth.search_index import InMemoryIndex

KEY = "documents/" + hashlib.sha256(PDF).hexdigest()


def _ingested(session_factory, store):
    with session_factory() as s:
        doc_id = ingest(s, store, PDF).id
        s.commit()
    return doc_id


def test_a_dry_run_does_not_wait_for_the_row(session_factory):
    store = SpyOriginalsStore()
    doc_id = _ingested(session_factory, store)
    with session_factory() as holder:
        holder.execute(select(Document.id).where(Document.id == doc_id)
                       .with_for_update())  # blocks any row lock
        with session_factory() as s:
            s.execute(text("SET lock_timeout = '2s'"))
            counts = delete_document(s, doc_id, store, InMemoryIndex(),
                                     actor="t", dry_run=True)
        holder.rollback()
    assert counts.object == 1
    assert store.objects.exists(KEY)  # a dry run removes nothing


def test_a_deletion_that_waited_sees_the_released_key(session_factory):
    store = SpyOriginalsStore()
    doc_id = _ingested(session_factory, store)
    errors, result = {}, {}

    def delete_again():
        with session_factory() as s:
            result["counts"] = delete_document(s, doc_id, store, InMemoryIndex(),
                                               actor="second")
            s.commit()

    with session_factory() as first:
        delete_document(first, doc_id, store, InMemoryIndex(), actor="first")
        first.flush()
        worker = run(errors, "second", delete_again)
        wait_for_a_lock_waiter(session_factory)
        first.commit()
    worker.join(30)

    assert not errors, errors
    assert result["counts"].object == 0
    with session_factory() as s:
        assert s.get(Document, doc_id).object_key == released_object_key(doc_id)
        steps = s.execute(select(AuditRecord.step).where(
            AuditRecord.document_id == doc_id)).scalars().all()
        assert steps.count("delete") == 1
