import pytest

from wordsworth.keys import InMemoryKeyProvider, KeyProvider, StubKeyProvider


def test_stub_satisfies_protocol():
    assert isinstance(StubKeyProvider("p"), KeyProvider)


def test_inmemory_satisfies_protocol():
    assert isinstance(InMemoryKeyProvider(), KeyProvider)


def test_rotate_adds_active_key_prior_versions_resolvable():
    kp = InMemoryKeyProvider()
    first = kp.current_key()
    second = kp.rotate()
    # the new key is now active...
    assert kp.current_key().id == second.id
    assert second.id != first.id
    # ...and prior versions remain resolvable by their key_id
    assert kp.key(first.id).material == first.material
    assert kp.key(second.id).material == second.material


def test_unknown_key_id_raises():
    with pytest.raises(KeyError):
        InMemoryKeyProvider().key("deadbeefdead")


def test_recovered_key_can_be_readmitted():
    kp = InMemoryKeyProvider()
    original = kp.current_key()
    fresh = InMemoryKeyProvider()  # does not know `original`
    with pytest.raises(KeyError):
        fresh.key(original.id)
    fresh.add(original)
    assert fresh.key(original.id).material == original.material


def test_stub_rotate_refuses_loudly():
    with pytest.raises(NotImplementedError):
        StubKeyProvider("p").rotate()


def test_deterministic_for_same_passphrase():
    a = StubKeyProvider("passphrase").current_key()
    b = StubKeyProvider("passphrase").current_key()
    assert a == b
    assert len(a.material) == 32


def test_different_passphrase_different_key():
    a = StubKeyProvider("alpha").current_key()
    b = StubKeyProvider("beta").current_key()
    assert a.material != b.material
    assert a.id != b.id
