# SPDX-License-Identifier: MIT
"""`delete-removes-original-scan` task 2: `doomed`'s row locks widen with the
claim -- a copy C whose `object_key` is a recovered document A's scan S must
be locked together with A, even though A's own row no longer points at S.
Without the widened lock, a concurrent deletion of A and C would each see the
other as live and keep S "for the other" (as `test_shred_locks.py` shows for
an ordinary copy and survivor)."""
from __future__ import annotations

import threading

import pytest
from psycopg.errors import LockNotAvailable
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from shred_setup import key_row, originals, wait_for_a_lock_waiter
from scan_setup import recover_now

from wordsworth import deletion_keys
from wordsworth.deletion import delete_document
from wordsworth.models import Document
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import ingest, register
from wordsworth.search_index import InMemoryIndex
from wordsworth.supersession import supersede


def _copy_and_recovered_survivor(session_factory, scanned_pdf, *, store):
    with session_factory() as s:
        survivor = ingest(s, store, scanned_pdf)
        s.commit()
        scan_key = survivor.object_key
        copy = register(s, scan_key)
        s.commit()
        supersede(s, copy.id, survivor.id, actor="t")
        s.commit()
        recover_now(s, store, survivor.id)
        return scan_key, survivor.id, copy.id


def _try_lock(session_factory, document_id) -> bool:
    with session_factory() as probe:
        try:
            probe.execute(select(Document.id).where(Document.id == document_id)
                          .with_for_update(key_share=True, nowait=True)).all()
            return True
        except OperationalError as exc:
            assert isinstance(exc.orig, LockNotAvailable)
            return False
        finally:
            probe.rollback()


def test_doomed_for_the_copy_also_locks_the_recovered_survivors_row(
        legacy_copies, scanned_pdf):
    """A's own row no longer points at S (it points at the OCR'd PDF), so
    only the new clause -- a recovering `ocr` record naming a candidate key --
    can find it from C's side. Without it, C's `doomed` would leave A's row
    unlocked and a concurrent deletion of A would not wait for it."""
    store = originals()
    scan_key, survivor_id, copy_id = _copy_and_recovered_survivor(
        legacy_copies, scanned_pdf, store=store)

    with legacy_copies() as holder:
        assert deletion_keys.doomed(holder, copy_id) == (scan_key, [])  # survivor live
        assert not _try_lock(legacy_copies, survivor_id)
        holder.rollback()
    assert _try_lock(legacy_copies, survivor_id)


@pytest.mark.parametrize("sealed_scan", [True, False])
def test_a_copy_and_its_recovered_survivor_deleted_at_once_leave_nothing(
        legacy_copies, scanned_pdf, sealed_scan):
    """A real concurrent deletion of the copy and the recovered survivor,
    once with S sealed (a key row to race over too) and once with S legacy
    plaintext (no key row -- only the row lock serialises them). Without the
    widened lock each deletion would keep S "for the other"."""
    store = originals() if sealed_scan else InMemoryObjectStore()
    scan_key, survivor_id, copy_id = _copy_and_recovered_survivor(
        legacy_copies, scanned_pdf, store=store)
    result: dict = {}

    def delete_survivor():
        with legacy_copies() as s:
            result["counts"] = delete_document(s, survivor_id, store,
                                               InMemoryIndex(), actor="b")
            s.commit()

    with legacy_copies() as first:
        copy_counts = delete_document(first, copy_id, store, InMemoryIndex(), actor="a")
        worker = threading.Thread(target=delete_survivor)
        worker.start()
        wait_for_a_lock_waiter(legacy_copies)
        first.commit()
    worker.join(timeout=30)

    assert not worker.is_alive()
    assert copy_counts.object == 0  # the survivor was still live then
    assert result["counts"].original_scan == 1
    assert not store.exists(scan_key)
    with legacy_copies() as s:
        assert key_row(s, scan_key) is None
