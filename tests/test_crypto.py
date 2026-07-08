import pytest

from wordsworth.crypto import decrypt, encrypt


def test_roundtrip():
    key = b"0" * 32
    ciphertext, nonce = encrypt(key, "geheim 123456782")
    assert decrypt(key, ciphertext, nonce) == "geheim 123456782"
    assert b"123456782" not in ciphertext  # stored as ciphertext, not plaintext


def test_wrong_key_fails_loudly():
    ciphertext, nonce = encrypt(b"0" * 32, "x")
    with pytest.raises(Exception):
        decrypt(b"1" * 32, ciphertext, nonce)
