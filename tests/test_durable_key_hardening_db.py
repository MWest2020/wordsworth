"""Durable key hardening — DB-integration (CI runs against real Postgres):
SessionFactoryKeyVaultStore round-trips, a fresh provider resolves persisted
keys, and the partial-unique index enforces one active key per scope."""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from wordsworth.keys import DurableKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.pseudonymizer import Pseudonymizer, _reveal
from wordsworth.transit import (
    FakeTransit,
    PostgresKeyVaultStore,
    SessionFactoryKeyVaultStore,
)

PII_BSN = "111222333"


def test_session_factory_store_roundtrip(session_factory):
    st = SessionFactoryKeyVaultStore(session_factory)
    wrapped = FakeTransit().wrap(b"k" * 32)
    st.put("k1", "PERSON", wrapped, "active")
    assert st.get("k1").key_id == "k1"
    assert st.active_for("PERSON").key_id == "k1"
    st.set_status("k1", "retired")
    assert st.active_for("PERSON") is None
    assert st.get("k1").status == "retired"


def test_fresh_provider_resolves_persisted_keys(session_factory):
    t = FakeTransit()
    st = SessionFactoryKeyVaultStore(session_factory)
    k = DurableKeyProvider(st, t).current_key("PERSON")     # persists (wrapped)
    k2 = DurableKeyProvider(st, t).key(k.id)                # fresh provider resolves
    assert k2.material == k.material


def test_partial_unique_index_rejects_second_active(session_factory):
    with session_factory() as s:
        PostgresKeyVaultStore(s).put("a", "BSN", b"x", "active")
        s.commit()
    with session_factory() as s:
        with pytest.raises(IntegrityError):
            PostgresKeyVaultStore(s).put("b", "BSN", b"y", "active")  # violates index
    # a retired row for the same scope is allowed
    with session_factory() as s:
        PostgresKeyVaultStore(s).put("c", "BSN", b"z", "retired")
        s.commit()
        assert PostgresKeyVaultStore(s).get("c").status == "retired"


def test_reveal_survives_via_singleton_over_session_factory(session_factory):
    """Pseudonymise in one request-session and reveal in another, through ONE
    process-lifetime provider over the session-factory vault — proves durability
    without a per-request provider."""
    t = FakeTransit()
    kp = DurableKeyProvider(SessionFactoryKeyVaultStore(session_factory), t)
    with session_factory() as s:
        text = Pseudonymizer(kp, PostgresMappingStore(s)).anonymize(f"BSN {PII_BSN}").text
        s.commit()
    assert PII_BSN not in text
    with session_factory() as s:
        restored, _ = _reveal(text, None, PostgresMappingStore(s).get, kp.key)
    assert PII_BSN in restored
