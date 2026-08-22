"""Process-lifetime key provider + one-active-key-per-scope — pure/local
(add-durable-key-hardening). No DB, no OpenBao."""
from __future__ import annotations

import pytest

from wordsworth.keys import DurableKeyProvider
from wordsworth.transit import (
    ActiveKeyExists,
    FakeTransit,
    InMemoryKeyVaultStore,
    VaultEntry,
)


class CountingTransit(FakeTransit):
    """FakeTransit that counts unwrap calls, to prove the cache warms."""

    def __init__(self) -> None:
        super().__init__()
        self.unwraps = 0

    def unwrap(self, ciphertext: bytes) -> bytes:
        self.unwraps += 1
        return super().unwrap(ciphertext)


def test_unwrap_cache_warms_within_one_provider():
    vault = InMemoryKeyVaultStore()
    DurableKeyProvider(vault, CountingTransit()).current_key("PERSON")  # mint
    t = CountingTransit()
    p = DurableKeyProvider(vault, t)                    # fresh provider, cold cache
    k = p.current_key("PERSON")
    p.current_key("PERSON")
    p.key(k.id)
    assert t.unwraps == 1                               # unwrapped once, then cached


def test_separate_providers_do_not_share_cache():
    vault = InMemoryKeyVaultStore()
    DurableKeyProvider(vault, CountingTransit()).current_key("PERSON")  # mint
    t = CountingTransit()
    DurableKeyProvider(vault, t).current_key("PERSON")  # cold
    DurableKeyProvider(vault, t).current_key("PERSON")  # cold again
    assert t.unwraps == 2                               # one unwrap per fresh provider


def test_one_active_after_rotate_old_still_resolvable():
    vault = InMemoryKeyVaultStore()
    p = DurableKeyProvider(vault, FakeTransit())
    k0 = p.current_key("BSN")
    k1 = p.rotate("BSN")
    assert k0.id != k1.id
    actives = [e for e in vault._d.values() if e.scope == "BSN" and e.status == "active"]
    assert [e.key_id for e in actives] == [k1.id]       # exactly one active
    assert vault.get(k0.id).status == "retired"
    assert p.key(k0.id).material == k0.material          # retired still decrypts


def test_store_rejects_second_active_for_scope():
    vault = InMemoryKeyVaultStore()
    vault.put("a", "BSN", b"x", "active")
    with pytest.raises(ActiveKeyExists):
        vault.put("b", "BSN", b"y", "active")
    vault.put("c", "BSN", b"z", "retired")              # a retired row is fine
    assert vault.get("c").status == "retired"


def test_current_key_adopts_winner_on_mint_race():
    """When a concurrent mint wins (the store rejects our second active), the
    provider adopts the winner instead of ending with two active keys."""
    winner = VaultEntry("winner", "PERSON", FakeTransit().wrap(b"w" * 32), "active")

    class Racy(InMemoryKeyVaultStore):
        def __init__(self) -> None:
            super().__init__()
            self._n = 0

        def active_for(self, scope: str):
            self._n += 1
            return None if self._n == 1 else winner      # none first, winner on re-read

        def put(self, *a, **k):
            raise ActiveKeyExists("race")                # our mint always loses

    k = DurableKeyProvider(Racy(), FakeTransit()).current_key("PERSON")
    assert k.id == "winner" and k.material == b"w" * 32


def test_reversible_wiring_shares_one_provider(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_REVERSIBLE", "true")
    from wordsworth.db import make_engine, make_session_factory
    from wordsworth.serve import _reversible_wiring

    wiring = _reversible_wiring(make_session_factory(make_engine()))  # no I/O
    kp = wiring["key_provider"]
    assert isinstance(kp, DurableKeyProvider)
    anon = wiring["anonymizer_factory"](None)            # session unused for the provider
    assert anon._keys is kp                              # ingest + reveal share one provider
