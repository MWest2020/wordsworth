# SPDX-License-Identifier: MIT
"""`originals-crypto-shred`: the row locks `deletion_keys.doomed` takes.

FOR NO KEY UPDATE, not FOR UPDATE: an ordinary audit append (advisory chain
lock, then a KEY SHARE lock on the document row through the foreign key) must
not deadlock with a deletion that holds the row lock and then waits for the
chain lock. The lock must still serialise two deletions on one object key,
also for a legacy plaintext object that has no key row."""
from __future__ import annotations

import threading

import pytest

from sqlalchemy import select, text

from shred_setup import KEY, key_row, originals, pair, sealed, wait_for_a_lock_waiter
from wordsworth import audit
from wordsworth.audit import current_state, verify_chain
from wordsworth.models import AuditRecord
from wordsworth.deletion import delete_document
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State


class _WaitingIndex(InMemoryIndex):
    """`exists` waits until released: the deletion then holds `doomed`'s row
    locks and has not reached its own audit append yet."""

    def __init__(self):
        super().__init__()
        self.entered, self.release = threading.Event(), threading.Event()

    def exists(self, document_id):
        self.entered.set()
        assert self.release.wait(30), "never released"
        return super().exists(document_id)


def _run(errors: dict, name: str, fn):
    def target():
        try:
            fn()
        except Exception as exc:  # surfaced by the assertion on `errors`
            errors[name] = exc
    thread = threading.Thread(target=target)
    thread.start()
    return thread


@pytest.mark.parametrize("append_to", ["the deleted document", "its survivor"])
def test_an_audit_append_during_a_deletion_commits_and_nothing_deadlocks(
        legacy_copies, append_to):
    store, _, survivor_id, copy_id = pair(legacy_copies)
    target = copy_id if append_to == "the deleted document" else survivor_id
    index, errors, appended = _WaitingIndex(), {}, threading.Event()

    def delete():
        with legacy_copies() as s:
            delete_document(s, copy_id, store, index, actor="t")
            s.commit()

    def append():
        with legacy_copies() as s:
            state = current_state(s, target).value
            audit.append(s, document_id=target, from_state=state, to_state=state,
                         step="detection_feedback", payload={"actor": "other"})
            s.commit()
        appended.set()

    deleting = _run(errors, "delete", delete)
    assert index.entered.wait(10)
    appending = _run(errors, "append", append)
    # Not blocked by the deletion's row lock: it commits while that is held.
    committed_while_held = appended.wait(5)
    index.release.set()
    deleting.join(30)
    appending.join(30)

    assert not errors, errors
    assert committed_while_held
    with legacy_copies() as s:
        assert current_state(s, copy_id) == State.DELETED
        assert verify_chain(s) == (True, None)


def test_a_plaintext_copy_and_its_survivor_deleted_at_once_leave_no_object(
        legacy_copies):
    """No key row, so only the documents lock serialises the two: without it
    each deletion keeps the object 'for the other'."""
    store, _, survivor_id, copy_id = pair(legacy_copies, plaintext=True)
    index, errors, result = InMemoryIndex(), {}, {}

    def delete_survivor():
        with legacy_copies() as s:
            result["counts"] = delete_document(s, survivor_id, store, index, actor="b")
            s.commit()

    with legacy_copies() as first:
        copy_counts = delete_document(first, copy_id, store, index, actor="a")
        worker = _run(errors, "survivor", delete_survivor)
        wait_for_a_lock_waiter(legacy_copies)
        first.commit()
    worker.join(30)

    assert not errors, errors
    assert copy_counts.object == 0  # the survivor was still live then
    assert result["counts"].object == 1 and result["counts"].keys_destroyed == 0
    assert not store.objects.exists(KEY)
    with legacy_copies() as s:
        assert key_row(s) is None


def test_a_key_moved_while_the_deletion_waited_is_read_again_under_the_lock(
        session_factory):
    """An OCR repoint (the row's object key moves from the scan to the OCR'd
    PDF) commits while the deletion waits for the row: `doomed` reads the key
    again under the lock, so the OCR'd PDF goes, the record names it, and
    both keys go -- not the scan, with the OCR'd object left behind."""
    ocr_key = "documents/" + "0c" * 32
    store = originals()
    with session_factory() as s:
        doc_id = sealed(s, store)
        sealed(s, store, key=ocr_key, data=b"%PDF-1.4 the OCR'd PDF", document_id=doc_id)
        s.commit()
    errors, result = {}, {}

    def delete():
        with session_factory() as s:
            result["counts"] = delete_document(s, doc_id, store, InMemoryIndex(), actor="t")
            s.commit()

    with session_factory() as rec:
        rec.execute(text("UPDATE documents SET object_key = :k WHERE id = :d"),
                    {"k": ocr_key, "d": doc_id})
        worker = _run(errors, "delete", delete)
        wait_for_a_lock_waiter(session_factory)
        rec.commit()
    worker.join(30)

    assert not errors, errors
    assert result["counts"].keys_destroyed == 2 and result["counts"].object == 1
    assert not store.objects.exists(ocr_key)
    with session_factory() as s:
        assert key_row(s, KEY) is None and key_row(s, ocr_key) is None
        rec = s.execute(select(AuditRecord).where(
            AuditRecord.document_id == doc_id, AuditRecord.step == "delete")).scalar_one()
        assert rec.payload["released_object_key"] == ocr_key
