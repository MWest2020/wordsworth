import pytest

from wordsworth.escrow import AgeEscrow, Escrow
from wordsworth.keys import InMemoryKeyProvider


def test_satisfies_protocol():
    assert isinstance(AgeEscrow(), Escrow)


def test_recover_returns_same_material():
    escrow = AgeEscrow()
    key = InMemoryKeyProvider().current_key()
    escrow.deposit(key)
    recovered = escrow.recover(key.id)
    assert recovered.id == key.id
    assert recovered.material == key.material


def test_recover_unknown_raises():
    with pytest.raises(KeyError):
        AgeEscrow().recover("nope")


def test_recover_rejects_tampered_id_binding():
    # key_id is bound as associated data; a mismatched id must fail to open.
    escrow = AgeEscrow()
    key = InMemoryKeyProvider().current_key()
    escrow.deposit(key)
    escrow._vault["other"] = escrow._vault[key.id]
    with pytest.raises(Exception):
        escrow.recover("other")
