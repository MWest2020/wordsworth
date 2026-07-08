from wordsworth.keys import KeyProvider, StubKeyProvider


def test_stub_satisfies_protocol():
    assert isinstance(StubKeyProvider("p"), KeyProvider)


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
