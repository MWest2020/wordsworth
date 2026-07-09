"""Key escrow and recovery behind a driver seam.

The included driver (``AgeEscrow``) uses age's own envelope construction —
X25519 key agreement + HKDF-SHA256 + ChaCha20-Poly1305 — built entirely from the
already-vendored ``cryptography`` library. Open, non-commercial, fully local: no
cloud API in the path, and CyberArk/Conjur are banned by contract. Production may
swap the ``age``/``sops`` CLI or OpenBao behind this same ``Escrow`` seam; the
driver contract is just ``deposit`` + ``recover``.

Key material is only ever held encrypted at rest here and is never logged."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .keys import Key

_HKDF_INFO = b"wordsworth-key-escrow"


@runtime_checkable
class Escrow(Protocol):
    def deposit(self, key: Key) -> None: ...
    def recover(self, key_id: str) -> Key: ...


@dataclass
class _Envelope:
    ephemeral_pub: bytes
    nonce: bytes
    ciphertext: bytes


def _derive(shared: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO
    ).derive(shared)


class AgeEscrow:
    """age-style escrow. ``deposit`` seals key material to the recipient public
    key; ``recover`` opens it with the held identity. The ``key_id`` is bound as
    associated data so an envelope cannot be replayed under a different id."""

    def __init__(self, identity: X25519PrivateKey | None = None):
        self._identity = identity or X25519PrivateKey.generate()
        self._recipient = self._identity.public_key()
        self._vault: dict[str, _Envelope] = {}

    def deposit(self, key: Key) -> None:
        ephemeral = X25519PrivateKey.generate()
        symmetric = _derive(ephemeral.exchange(self._recipient))
        nonce = os.urandom(12)
        ciphertext = ChaCha20Poly1305(symmetric).encrypt(
            nonce, key.material, key.id.encode("utf-8")
        )
        self._vault[key.id] = _Envelope(
            ephemeral_pub=ephemeral.public_key().public_bytes(
                serialization.Encoding.Raw, serialization.PublicFormat.Raw
            ),
            nonce=nonce,
            ciphertext=ciphertext,
        )

    def recover(self, key_id: str) -> Key:
        envelope = self._vault.get(key_id)
        if envelope is None:
            raise KeyError(f"no escrowed key: {key_id}")
        ephemeral_pub = X25519PublicKey.from_public_bytes(envelope.ephemeral_pub)
        symmetric = _derive(self._identity.exchange(ephemeral_pub))
        material = ChaCha20Poly1305(symmetric).decrypt(
            envelope.nonce, envelope.ciphertext, key_id.encode("utf-8")
        )
        return Key(id=key_id, material=material)
