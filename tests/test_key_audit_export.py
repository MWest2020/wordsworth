"""WORM export of the key-lifecycle stream (gap 28).

This is the stream that says who issued, revoked or rotated what, and when. The
question arrives after an incident, when the host that holds the stream is
itself suspect -- so it has to end up somewhere it can no longer be changed.
Since key-audit-in-postgres the source is the chained table, not a file.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from wordsworth import key_audit_pg
from wordsworth.audit_export import ExportError, InMemoryWormStore
from wordsworth.key_audit_export import export_key_lifecycle_worm
from wordsworth.key_audit_pg import PostgresKeyLifecycleAudit


def _rotations(session, n):
    a = PostgresKeyLifecycleAudit(session)
    for i in range(n):
        a.rotation(old_key_id=f"k{i}", new_key_id=f"k{i+1}",
                   entries_reencrypted=i, actor="operator")
    session.commit()


def test_the_stream_lands_behind_object_lock(session):
    _rotations(session, 2)
    store = InMemoryWormStore()
    res = export_key_lifecycle_worm(session, store, retention_days=3650)
    assert res.count == 2
    assert res.object_key.startswith("key-lifecycle/seq-")
    # The stored object is the table serialised one way, byte for byte.
    assert store.get(res.object_key).decode() == key_audit_pg.export_jsonl(session)


def test_an_exported_object_verifies_without_the_database(session):
    """The export_jsonl docstring promises this; here is the promise kept."""
    _rotations(session, 3)
    store = InMemoryWormStore()
    res = export_key_lifecycle_worm(session, store, retention_days=3650)
    stored = store.get(res.object_key).decode()
    assert key_audit_pg.verify_jsonl(stored) == (True, None)
    forged = stored.replace('"actor": "operator"', '"actor": "someone"', 1)
    assert key_audit_pg.verify_jsonl(forged) == (False, res.first_seq)


def test_the_retention_is_on_the_object(session):
    _rotations(session, 1)
    store = InMemoryWormStore()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    res = export_key_lifecycle_worm(session, store, retention_days=2555, now=now)
    assert res.retain_until == now + timedelta(days=2555)
    assert store.retain_until(res.object_key) == res.retain_until


def test_incremental_export_ships_only_what_is_new(session):
    _rotations(session, 2)
    store = InMemoryWormStore()
    first = export_key_lifecycle_worm(session, store, retention_days=3650)
    PostgresKeyLifecycleAudit(session).rotation(
        old_key_id="k2", new_key_id="k3", entries_reencrypted=7, actor="operator")
    session.commit()
    second = export_key_lifecycle_worm(session, store, retention_days=3650,
                                       after_seq=first.last_seq)
    assert second.count == 1
    body = store.get(second.object_key).decode()
    assert '"k3"' in body and '"k1"' not in body
    # The slice chains onto the previous export's last hash.
    prev = key_audit_pg.hash_before(session, first.last_seq)
    assert key_audit_pg.verify_jsonl(body, prev_hash=prev) == (True, None)


def test_a_gap_in_seq_does_not_miscount(session):
    """A rolled-back event still consumed a sequence number."""
    _rotations(session, 1)
    PostgresKeyLifecycleAudit(session).grant_revoked(grant_id="g", actor="x")
    session.rollback()
    _rotations(session, 1)
    res = export_key_lifecycle_worm(session, InMemoryWormStore(), retention_days=3650)
    assert res.count == 2
    assert res.last_seq - res.first_seq == 2


def test_nothing_new_is_not_an_error(session):
    # A stream that stood still is not a failed export. This distinction is why
    # a scheduled run does not raise an alarm every night.
    _rotations(session, 2)
    store = InMemoryWormStore()
    first = export_key_lifecycle_worm(session, store, retention_days=3650)
    res = export_key_lifecycle_worm(session, store, retention_days=3650,
                                    after_seq=first.last_seq)
    assert res.count == 0 and res.object_key is None


def test_an_empty_stream_exports_nothing(session):
    res = export_key_lifecycle_worm(session, InMemoryWormStore(), retention_days=3650)
    assert res.count == 0 and res.object_key is None


def test_a_store_that_returns_something_else_is_a_hard_error(session):
    class Lying(InMemoryWormStore):
        def get(self, key):
            return b"something else\n"

    _rotations(session, 1)
    with pytest.raises(ExportError, match="does not match"):
        export_key_lifecycle_worm(session, Lying(), retention_days=3650)


def test_a_broken_chain_is_not_exported(session):
    """The old file export shipped whatever the file said. Not any more."""
    _rotations(session, 2)
    session.execute(text("ALTER TABLE key_lifecycle_events "
                         "DISABLE TRIGGER key_lifecycle_no_mutation"))
    session.execute(text("UPDATE key_lifecycle_events SET actor = 'someone'"))
    session.execute(text("ALTER TABLE key_lifecycle_events "
                         "ENABLE TRIGGER key_lifecycle_no_mutation"))
    session.commit()
    store = InMemoryWormStore()
    with pytest.raises(ExportError, match="does not verify"):
        export_key_lifecycle_worm(session, store, retention_days=3650)


def test_grants_are_in_it_too(session):
    # The stream carries more than rotations: issuing and revoking grants belong
    # to the same question ("who was allowed what, when").
    a = PostgresKeyLifecycleAudit(session)
    a.grant_issued(grant_id="g1", recipient="r", allowed_types=["BSN"],
                   document_id=None, actor="operator")
    a.grant_revoked(grant_id="g1", actor="operator")
    session.commit()
    store = InMemoryWormStore()
    res = export_key_lifecycle_worm(session, store, retention_days=3650)
    body = store.get(res.object_key).decode()
    assert "grant_issued" in body and "grant_revoked" in body
    # And no key material -- the stream carries ids, never keys.
    assert "BEGIN" not in body
