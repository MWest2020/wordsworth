# SPDX-License-Identifier: MIT
"""The sealed-object format for original PDFs (ADR-0008): a versioned header
followed by AES-256-GCM ciphertext. ``seal``/``open`` are the only way the
bytes are produced or consumed; everything else (the key store, the
object-store guard) lives in its own module.

Header: ``WWENC`` (5 bytes) + version (1 byte) + ``key_id`` (12 ASCII bytes,
the same 12-hex-character ids the key stores mint) + nonce (12 bytes), then
the GCM ciphertext with its 16-byte tag.

The associated data is ``b"wordsworth-original/1" || object_key || key_id``
(design.md §3) -- never the document id: an object can legitimately belong to
more than one document over its life (a superseded copy, a re-ingest after
deletion), and binding the document id would force a re-seal at every change
of owner. Binding the object key and key id still makes a sealed object fail
to open when it is copied or swapped to another key, or when its header's
key id is changed."""
from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HEADER_MAGIC = b"WWENC"
VERSION = 1
_KEY_ID_LEN = 12
_NONCE_LEN = 12
_KEY_ID_START = len(HEADER_MAGIC) + 1
_NONCE_START = _KEY_ID_START + _KEY_ID_LEN
HEADER_LEN = _NONCE_START + _NONCE_LEN  # 30

_AAD_PREFIX = b"wordsworth-original/1"


def _aad(object_key: str, key_id: str) -> bytes:
    return _AAD_PREFIX + object_key.encode("utf-8") + key_id.encode("ascii")


def seal(dek: bytes, key_id: str, object_key: str, plaintext: bytes) -> bytes:
    """Seal ``plaintext`` under the 32-byte ``dek``, for ``object_key``, with
    the header naming ``key_id``. A fresh random nonce every call."""
    key_id_bytes = key_id.encode("ascii")
    if len(key_id_bytes) != _KEY_ID_LEN:
        raise ValueError(f"key_id must be {_KEY_ID_LEN} ASCII bytes: {key_id!r}")
    nonce = os.urandom(_NONCE_LEN)
    header = HEADER_MAGIC + bytes([VERSION]) + key_id_bytes + nonce
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext, _aad(object_key, key_id))
    return header + ciphertext


def header_key_id(sealed: bytes) -> str:
    """The key id named in a sealed header, without opening it (used by
    ``put_original`` to decide which of its five rules applies). Raises if
    the bytes do not carry a wordsworth sealed header."""
    if len(sealed) < HEADER_LEN or sealed[:len(HEADER_MAGIC)] != HEADER_MAGIC:
        raise ValueError("not a sealed wordsworth original")
    if sealed[len(HEADER_MAGIC)] != VERSION:
        raise ValueError(f"unsupported envelope version: {sealed[len(HEADER_MAGIC)]}")
    return sealed[_KEY_ID_START:_NONCE_START].decode("ascii")


def open(dek: bytes, key_id: str, object_key: str, sealed: bytes) -> bytes:
    """Open ``sealed`` bytes under the 32-byte ``dek``, expected for
    ``object_key`` and header ``key_id``. Fails closed -- raises and returns
    no plaintext -- on a flipped byte, a changed header key id, or bytes
    sealed for another object key: all three change what the GCM tag
    authenticates (the ciphertext, or the associated data), so a mismatch is
    never silently accepted."""
    actual_key_id = header_key_id(sealed)
    if actual_key_id != key_id:
        raise ValueError(
            f"sealed header names key_id {actual_key_id!r}, expected {key_id!r}")
    nonce = sealed[_NONCE_START:HEADER_LEN]
    ciphertext = sealed[HEADER_LEN:]
    return AESGCM(dek).decrypt(nonce, ciphertext, _aad(object_key, key_id))
