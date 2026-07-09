import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from wordsworth import audit, audit_export
from wordsworth.audit_export import (
    ExportError,
    InMemoryWormStore,
    WormObjectStore,
    WormRetentionError,
    export_worm,
    verify_export,
)
from wordsworth.models import Document


def _doc(session):
    doc = Document(object_key="k")
    session.add(doc)
    session.flush()
    return doc.id


def _seed(session, n=2):
    did = _doc(session)
    prev = None
    for i in range(n):
        state = f"s{i}"
        audit.append(session, document_id=did, from_state=prev,
                     to_state=state, step=f"step{i}", payload={"i": i})
        prev = state
    session.commit()
    return did


def test_inmemory_double_is_a_worm_store():
    assert isinstance(InMemoryWormStore(), WormObjectStore)


# --- 1. WORM export ---------------------------------------------------------

def test_export_writes_retention_locked_object(session):
    _seed(session, 2)
    store = InMemoryWormStore()
    res = export_worm(session, store, retention_days=3650)

    assert res.count == 2 and res.first_seq == 1 and res.last_seq == 2
    assert res.object_key is not None
    # The object carries a retention lock roughly 10 years out.
    lock = store.retain_until(res.object_key)
    assert lock is not None and lock > datetime.now(timezone.utc) + timedelta(days=3600)


def test_locked_object_cannot_be_overwritten_or_deleted():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store = InMemoryWormStore(now=now)
    store.put_object_locked("k", b"a", now + timedelta(days=10))
    with pytest.raises(WormRetentionError):
        store.put_object_locked("k", b"b", now + timedelta(days=10))
    with pytest.raises(WormRetentionError):
        store.delete("k")
    assert store.get("k") == b"a"  # unchanged


def test_lock_releases_only_after_expiry():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store = InMemoryWormStore(now=now)
    store.put_object_locked("k", b"a", now + timedelta(days=10))
    store.now = now + timedelta(days=11)  # past expiry
    store.put_object_locked("k", b"b", store.now + timedelta(days=10))
    assert store.get("k") == b"b"


# --- 1.2 Incremental --------------------------------------------------------

def test_incremental_exports_only_new_records(session):
    _seed(session, 2)
    store = InMemoryWormStore()
    first = export_worm(session, store, retention_days=3650)
    assert first.count == 2

    audit.append(session, document_id=_doc(session), from_state=None,
                 to_state="more", step="later", payload={})
    session.commit()

    second = export_worm(session, store, retention_days=3650, after_seq=first.last_seq)
    assert second.count == 1 and second.first_seq == 3 and second.last_seq == 3
    assert second.object_key != first.object_key
    # The incremental object holds only the one new record.
    body = store.get(second.object_key).splitlines()
    assert len(body) == 1 and json.loads(body[0])["seq"] == 3


def test_nothing_new_writes_nothing(session):
    _seed(session, 2)
    store = InMemoryWormStore()
    res = export_worm(session, store, retention_days=3650, after_seq=2)
    assert res.count == 0 and res.object_key is None


# --- 2. Verification --------------------------------------------------------

def test_matching_export_verifies(session):
    _seed(session, 3)
    jsonl = audit.export_jsonl(session)
    assert verify_export(session, jsonl) is True


def test_altered_export_is_rejected(session):
    _seed(session, 2)
    jsonl = audit.export_jsonl(session)
    lines = jsonl.splitlines()
    tampered = json.loads(lines[0])
    tampered["payload"] = {"i": 9999}
    lines[0] = json.dumps(tampered, sort_keys=True, ensure_ascii=False)
    assert verify_export(session, "\n".join(lines)) is False


def test_partial_export_is_rejected(session):
    _seed(session, 3)
    lines = audit.export_jsonl(session).splitlines()
    assert verify_export(session, "\n".join(lines[:-1])) is False  # dropped last


def test_export_fails_when_database_chain_is_tampered(session):
    _seed(session, 2)
    session.execute(text("ALTER TABLE audit_records DISABLE TRIGGER audit_no_mutation"))
    session.execute(text(
        "UPDATE audit_records SET payload = '{\"i\": 9999}' "
        "WHERE seq = (SELECT min(seq) FROM audit_records)"
    ))
    session.execute(text("ALTER TABLE audit_records ENABLE TRIGGER audit_no_mutation"))
    session.commit()
    with pytest.raises(ExportError):
        export_worm(session, InMemoryWormStore(), retention_days=3650)


# --- 3. Retention -----------------------------------------------------------

def test_retention_period_is_configurable_per_bewaartermijn(session):
    _seed(session, 1)
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store = InMemoryWormStore(now=now)
    res = export_worm(session, store, retention_days=2555, now=now)  # ~7 years
    assert res.retain_until == now + timedelta(days=2555)
