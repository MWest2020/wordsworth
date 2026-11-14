# SPDX-License-Identifier: MIT
"""`originals-crypto-shred`: a key follows its object. A superseded copy
shares its object key with its survivor, so the key goes only with the last
claim -- also when the two are deleted at the same moment."""
from __future__ import annotations

import threading

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from shred_setup import KEY, PDF, key_row, originals, pair, wait_for_a_lock_waiter
from wordsworth import deletion_keys
from wordsworth.deletion import delete_document
from wordsworth.search_index import InMemoryIndex


def _opens_cold(session, store, transit):
    """The original through a fresh key store: the key row is what opens it."""
    return originals(transit, store.objects).get_original(session, KEY)


@pytest.mark.parametrize("row_carries", ["survivor", "copy"])
def test_deleting_the_copy_leaves_the_survivors_key(legacy_copies, row_carries):
    store, transit, survivor_id, copy_id = pair(legacy_copies, row_carries=row_carries)
    with legacy_copies() as s:
        counts = delete_document(s, copy_id, store, InMemoryIndex(), actor="t")
        s.commit()
        assert counts.keys_destroyed == 0 and counts.object == 0
        assert key_row(s) is not None
        assert _opens_cold(s, store, transit) == PDF


def test_the_key_goes_with_the_last_claim(legacy_copies):
    store, transit, survivor_id, copy_id = pair(legacy_copies)
    index = InMemoryIndex()
    with legacy_copies() as s:
        first = delete_document(s, survivor_id, store, index, actor="t")
        s.commit()
        assert first.keys_destroyed == 0 and first.object == 0
        assert store.objects.exists(KEY) and key_row(s) is not None

        second = delete_document(s, copy_id, store, index, actor="t")
        s.commit()
        assert second.keys_destroyed == 1 and second.object == 1
        assert not store.objects.exists(KEY) and key_row(s) is None


def test_the_second_deletion_waits_for_the_lock_of_the_first(legacy_copies):
    """The first runs `doomed` for the copy and does not commit; the second,
    with a short lock_timeout, cannot get the lock (only `doomed` has run, so
    the row locks are the only locks held); the first then finishes its
    deletion and commits, the second runs and both object and key go."""
    store, _, survivor_id, copy_id = pair(legacy_copies)
    index = InMemoryIndex()
    first, second = legacy_copies(), legacy_copies()
    try:
        assert deletion_keys.doomed(first, copy_id) == (KEY, [])  # survivor live
        second.execute(text("SET lock_timeout = '200ms'"))
        with pytest.raises(OperationalError, match="lock timeout"):
            delete_document(second, survivor_id, store, index, actor="b")
        second.rollback()
        assert store.objects.exists(KEY)  # the refusal came before the object

        delete_document(first, copy_id, store, index, actor="a")
        first.commit()
        counts = delete_document(second, survivor_id, store, index, actor="b")
        second.commit()
    finally:
        first.close()
        second.close()
    assert counts.keys_destroyed == 1
    assert not store.objects.exists(KEY)
    with legacy_copies() as s:
        assert key_row(s) is None


def test_a_copy_and_its_survivor_deleted_at_the_same_moment_leave_nothing(
        legacy_copies):
    """Two real concurrent deletions: the second blocks on the first's row
    locks and, once the first commits, reads the committed state. Without
    the lock each would keep the object and the key 'for the other'."""
    store, _, survivor_id, copy_id = pair(legacy_copies)
    index = InMemoryIndex()
    result: dict = {}

    def delete_survivor():
        try:
            with legacy_copies() as s:
                result["counts"] = delete_document(s, survivor_id, store, index,
                                                   actor="b")
                s.commit()
        except Exception as exc:  # surfaced by the assertion below
            result["error"] = exc

    with legacy_copies() as first:
        copy_counts = delete_document(first, copy_id, store, index, actor="a")
        worker = threading.Thread(target=delete_survivor)
        worker.start()
        wait_for_a_lock_waiter(legacy_copies)
        first.commit()
    worker.join(timeout=30)

    assert not worker.is_alive() and "error" not in result, result
    assert copy_counts.keys_destroyed == 0  # the survivor was still live then
    assert result["counts"].keys_destroyed == 1
    assert not store.objects.exists(KEY)
    with legacy_copies() as s:
        assert key_row(s) is None
