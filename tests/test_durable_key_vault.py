"""Durable envelope-wrapped key vault — pure/local, no DB, no server (ADR-0002).

Proves keys survive a "restart" (a fresh provider over the same vault + transit)
using a FakeTransit KEK and InMemoryKeyVaultStore. The DB-backed path is in
tests/test_durable_key_vault_db.py (CI, real Postgres)."""
from __future__ import annotations

import pytest

from wordsworth.keys import DEFAULT_SCOPE, DurableKeyProvider, KeyProvider
from wordsworth.mapping_store import InMemoryMappingStore
from wordsworth.pseudonymizer import Pseudonymizer, _reveal
from wordsworth.transit import FakeTransit, InMemoryKeyVaultStore

PII_BSN = "123456782"
PII_EMAIL = "jan@example.nl"


def _provider():
    return DurableKeyProvider(InMemoryKeyVaultStore(), FakeTransit())


def test_satisfies_key_provider_protocol():
    assert isinstance(_provider(), KeyProvider)


def test_current_key_mints_and_persists_only_wrapped():
    vault, transit = InMemoryKeyVaultStore(), FakeTransit()
    kp = DurableKeyProvider(vault, transit)
    key = kp.current_key(scope="PERSON")
    entry = vault.active_for("PERSON")
    assert entry is not None and entry.key_id == key.id
    assert entry.wrapped_material != key.material          # only wrapped is stored
    assert transit.unwrap(entry.wrapped_material) == key.material


def test_durability_fresh_provider_resolves_persisted_keys():
    vault, transit = InMemoryKeyVaultStore(), FakeTransit()
    first = DurableKeyProvider(vault, transit)
    key = first.current_key(scope="PERSON")

    # a "restart": brand-new provider, same vault + transit, empty cache
    second = DurableKeyProvider(vault, transit)
    assert second.current_key(scope="PERSON").material == key.material
    assert second.key(key.id).material == key.material


def test_rotate_retires_old_keeps_it_resolvable_and_isolates_scope():
    vault, transit = InMemoryKeyVaultStore(), FakeTransit()
    kp = DurableKeyProvider(vault, transit)
    person0 = kp.current_key(scope="PERSON")
    bsn0 = kp.current_key(scope="BSN")

    person1 = kp.rotate(scope="PERSON")
    assert person1.id != person0.id
    assert kp.current_key(scope="PERSON").id == person1.id        # new active
    assert kp.key(person0.id).material == person0.material        # retired resolvable
    assert vault.get(person0.id).status == "retired"
    assert kp.current_key(scope="BSN").id == bsn0.id              # other scope untouched


def test_unknown_key_id_raises():
    with pytest.raises(KeyError):
        _provider().key("nope")


def test_end_to_end_reveal_survives_restart():
    vault, transit = InMemoryKeyVaultStore(), FakeTransit()
    mappings = InMemoryMappingStore()
    pseudo = Pseudonymizer(DurableKeyProvider(vault, transit), mappings).anonymize(
        f"BSN {PII_BSN} mail {PII_EMAIL}"
    ).text
    assert PII_BSN not in pseudo and PII_EMAIL not in pseudo
    # "restart": a brand-new provider (cold cache) over the SAME vault + transit
    fresh = DurableKeyProvider(vault, transit)
    restored, _ = _reveal(pseudo, None, mappings.get, fresh.key)
    assert PII_BSN in restored and PII_EMAIL in restored


def test_unwrap_failure_is_fail_closed_no_clear_fallback():
    class BoomTransit:
        def wrap(self, plaintext):
            return b"wrapped"
        def unwrap(self, ciphertext):
            raise RuntimeError("transit unavailable")

    vault = InMemoryKeyVaultStore()
    vault.put("kid", "PERSON", b"wrapped", "active")
    kp = DurableKeyProvider(vault, BoomTransit())
    with pytest.raises(RuntimeError):
        kp.key("kid")           # raises, never returns a clear-key fallback
    with pytest.raises(RuntimeError):
        kp.current_key(scope="PERSON")
