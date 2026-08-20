"""Durable key vault against a real Postgres (ADR-0002) — runs in CI."""
from __future__ import annotations

from wordsworth import audit
from wordsworth.keys import DurableKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.pipeline import register
from wordsworth.pseudonymizer import Pseudonymizer, deanonymize
from wordsworth.transit import FakeTransit, PostgresKeyVaultStore

PII_BSN = "123456782"
PII_EMAIL = "jan@example.nl"


def test_postgres_vault_roundtrip(session):
    store = PostgresKeyVaultStore(session)
    store.put("k1", "PERSON", b"wrapped-1", "active")
    session.commit()
    assert store.get("k1").scope == "PERSON"
    assert store.active_for("PERSON").key_id == "k1"
    store.set_status("k1", "retired")
    session.commit()
    assert store.get("k1").status == "retired"
    assert store.active_for("PERSON") is None


def test_reveal_survives_restart_with_postgres_vault(session):
    transit = FakeTransit()
    vault = PostgresKeyVaultStore(session)
    doc = register(session, "d")
    session.commit()

    result = Pseudonymizer(
        DurableKeyProvider(vault, transit), PostgresMappingStore(session)
    ).anonymize(f"BSN {PII_BSN} mail {PII_EMAIL}")
    session.commit()
    for secret in (PII_BSN, PII_EMAIL):
        assert secret not in result.text

    # a fresh provider (cold cache) re-unwraps the persisted wrapped keys
    fresh = DurableKeyProvider(vault, transit)
    restored = deanonymize(
        session, doc.id, result.text, fresh, PostgresMappingStore(session),
        actor="mark",
    )
    session.commit()
    for secret in (PII_BSN, PII_EMAIL):
        assert secret in restored
    ok, bad = audit.verify_chain(session)
    assert ok is True and bad is None
