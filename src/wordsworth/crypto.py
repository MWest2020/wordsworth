"""AES-GCM encrypt/decrypt helpers. A fresh random nonce per record."""
from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt(key: bytes, plaintext: str) -> tuple[bytes, bytes]:
    """Return (ciphertext, nonce)."""
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return ciphertext, nonce


def decrypt(key: bytes, ciphertext: bytes, nonce: bytes) -> str:
    return AESGCM(key).decrypt(nonce, ciphertext, None).decode("utf-8")
