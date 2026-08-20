"""Selective, key-gated reveal — pure/local (no DB) (add-per-type-keyed-reveal).

Pseudonymizer.anonymize and the reveal substitution need only a KeyProvider and a
MappingStore, so the full pseudonymise → selective-reveal loop is provable in
memory. The DB-backed audit path of deanonymize() is covered in
tests/test_pseudonymizer.py (CI runs it against a real Postgres)."""
from __future__ import annotations

from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import InMemoryMappingStore, MappingStore
from wordsworth.pseudonymizer import Pseudonymizer, _reveal

# 111222333 passes the BSN elfproef; a plain address for the email detector.
CLEAR = "BSN 111222333 en mail jan@example.nl"


def _pseudonymize():
    kp = InMemoryKeyProvider()
    store = InMemoryMappingStore()
    pseudo = Pseudonymizer(kp, store).anonymize(CLEAR).text
    return kp, store, pseudo


def test_in_memory_store_satisfies_protocol():
    assert isinstance(InMemoryMappingStore(), MappingStore)


def test_index_text_has_no_clear_pii():
    _, _, pseudo = _pseudonymize()
    assert "111222333" not in pseudo
    assert "jan@example.nl" not in pseudo
    assert "[BSN:" in pseudo and "[EMAIL:" in pseudo


def test_reveal_all_recovers_everything():
    kp, store, pseudo = _pseudonymize()
    restored, revealed = _reveal(pseudo, None, store.get, kp.key)
    assert "111222333" in restored and "jan@example.nl" in restored
    assert len(revealed) == 2


def test_reveal_only_allowed_type():
    kp, store, pseudo = _pseudonymize()
    restored, revealed = _reveal(pseudo, {"EMAIL"}, store.get, kp.key)
    assert "jan@example.nl" in restored      # allowed → revealed
    assert "111222333" not in restored       # not allowed → stays token
    assert "[BSN:" in restored
    assert all(r.startswith("[EMAIL:") for r in revealed)


def test_type_without_key_stays_pseudonymised():
    kp, store, pseudo = _pseudonymize()
    email_key_id = kp.current_key(scope="EMAIL").id

    def only_email_key(key_id: str):
        if key_id == email_key_id:
            return kp.key(key_id)
        raise KeyError(key_id)              # caller lacks BSN's key

    # all types allowed, but only the EMAIL key is resolvable
    restored, revealed = _reveal(pseudo, None, store.get, only_email_key)
    assert "jan@example.nl" in restored
    assert "111222333" not in restored
    assert all(r.startswith("[EMAIL:") for r in revealed)


def test_per_type_keys_do_not_cross_decrypt():
    kp, store, pseudo = _pseudonymize()
    # The BSN mapping's key must not be the EMAIL key.
    bsn_token = next(p for p in store._d if p.startswith("[BSN:"))
    email_token = next(p for p in store._d if p.startswith("[EMAIL:"))
    assert store.get(bsn_token).key_id != store.get(email_token).key_id
