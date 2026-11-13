# SPDX-License-Identifier: MIT
"""`originals-crypto-shred` task 1: the unwrap cache trusts a cached key only
while its key row exists with the same `key_id`, read from the database on
every call -- so a delete holds on every replica at once."""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import text

from shred_setup import KEY, CountingTransit, keys_over, sealed, originals
from wordsworth.db import make_engine
from wordsworth.document_keys import DocumentKeyRecord, OriginalsKeyUnavailable


def _seal_and_commit(session_factory):
    transit = CountingTransit()
    store = originals(transit)
    with session_factory() as s:
        doc_id = sealed(s, store)
        s.commit()
    return doc_id, transit


def _destroy_row(session_factory):
    """Another process (the replica that ran the delete) removes the row."""
    with session_factory() as other:
        other.execute(sa_delete(DocumentKeyRecord)
                      .where(DocumentKeyRecord.object_key == KEY))
        other.commit()


def test_a_cached_key_with_its_row_unchanged_calls_the_key_service_once(
        session_factory):
    _, transit = _seal_and_commit(session_factory)
    keys = keys_over(transit)
    with session_factory() as s:
        first = keys.unwrap(s, KEY)
        second = keys.unwrap(s, KEY)
    assert first == second
    assert transit.unwraps == 1


def test_evict_drops_the_entry_and_the_next_unwrap_calls_the_key_service(
        session_factory):
    _, transit = _seal_and_commit(session_factory)
    keys = keys_over(transit)
    with session_factory() as s:
        keys.unwrap(s, KEY)
        assert transit.unwraps == 1
        keys.evict([KEY])
        keys.unwrap(s, KEY)  # the row still exists: a real unwrap again
    assert transit.unwraps == 2


def test_evict_touches_nothing_else(session_factory):
    other_key = "documents/" + "6e" * 32
    transit = CountingTransit()
    store = originals(transit)
    with session_factory() as s:
        sealed(s, store)
        sealed(s, store, key=other_key, data=b"%PDF-1.4 another")
        s.commit()
    keys = keys_over(transit)
    with session_factory() as s:
        keys.unwrap(s, KEY)
        keys.unwrap(s, other_key)
        keys.evict([KEY, "documents/never-cached"])
        keys.unwrap(s, other_key)
    assert transit.unwraps == 2  # other_key still served from the cache


def test_another_replica_cannot_unwrap_after_the_row_is_destroyed(
        session_factory):
    """Two `DocumentKeys` instances on one database, as two API replicas.
    The second caches the key; the first's session deletes the row and
    commits; within the TTL the second raises, without a key-service call."""
    _, transit = _seal_and_commit(session_factory)
    replica_a = keys_over(transit, cache_ttl=300)
    replica_b = keys_over(transit, cache_ttl=300)
    with session_factory() as sb:
        replica_b.unwrap(sb, KEY)
        with session_factory() as sa:
            replica_a.unwrap(sa, KEY)
            sa.execute(sa_delete(DocumentKeyRecord)
                       .where(DocumentKeyRecord.object_key == KEY))
            sa.commit()
        calls = transit.unwraps
        with pytest.raises(OriginalsKeyUnavailable):
            replica_b.unwrap(sb, KEY)
        assert transit.unwraps == calls
        assert KEY not in replica_b._cache  # the stale entry is dropped


def test_a_key_destroyed_and_minted_again_is_not_served_from_the_old_entry(
        session_factory):
    doc_id, transit = _seal_and_commit(session_factory)
    replica_a = keys_over(transit)
    replica_b = keys_over(transit)
    with session_factory() as sb:
        old = replica_b.unwrap(sb, KEY)
        _destroy_row(session_factory)
        with session_factory() as sa:
            new = replica_a.mint(sa, doc_id, KEY, "default")
            sa.commit()
        assert new.key_id != old.key_id
        got = replica_b.unwrap(sb, KEY)
    assert got == new


def test_the_miss_path_does_not_answer_from_the_identity_map(session_factory):
    """One session loads the row, another deletes it and commits; with an
    empty cache, `unwrap` on the first session must not find the row it
    still holds in memory, and must not call the key service."""
    _, transit = _seal_and_commit(session_factory)
    keys = keys_over(transit)
    with session_factory() as s:
        held = s.get(DocumentKeyRecord, KEY)  # a strong ref keeps it mapped
        assert held is not None
        _destroy_row(session_factory)
        calls = transit.unwraps
        with pytest.raises(OriginalsKeyUnavailable):
            keys.unwrap(s, KEY)
    assert transit.unwraps == calls


def test_the_miss_path_does_not_return_a_destroyed_key_held_in_the_session(
        session_factory):
    """`populate_existing`: a session that loaded the key row earlier must not
    get the old, destroyed key back after another process destroyed and
    minted it again under the same object key."""
    doc_id, transit = _seal_and_commit(session_factory)
    keys = keys_over(transit)
    with session_factory() as s:
        held = s.get(DocumentKeyRecord, KEY)  # the old row, kept mapped
        old_key_id = held.key_id
        _destroy_row(session_factory)
        with session_factory() as other:
            new = keys_over(transit).mint(other, doc_id, KEY, "default")
            other.commit()
        got = keys.unwrap(s, KEY)
    assert new.key_id != old_key_id
    assert got.key_id == new.key_id and got.material == new.material


def test_the_engine_runs_read_committed(session_factory):
    """`unwrap`'s row check relies on each statement seeing what was
    committed before it started."""
    with session_factory() as s:
        level = s.execute(text("SHOW transaction_isolation")).scalar_one()
    assert level == "read committed"


def test_read_committed_holds_against_a_server_side_default(database_url):
    """`make_engine` sets the level itself, so a database or role default of
    REPEATABLE READ (simulated here per connection) cannot bypass the check."""
    engine = make_engine(database_url)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql(
                "SET SESSION default_transaction_isolation = 'repeatable read'")
            conn.commit()
            level = conn.exec_driver_sql("SHOW transaction_isolation").scalar_one()
    finally:
        engine.dispose()
    assert level == "read committed"
