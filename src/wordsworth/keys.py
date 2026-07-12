"""Key provider seam. Keys are versioned by ``key_id``: a provider holds a
current (active) key, resolves any prior version by id, and can ``rotate`` to a
new active key without destroying old ones. Deanonymization selects the key by
the mapping's stored ``key_id``, so entries under any version decrypt.

Escrow/recovery live behind the ``Escrow`` seam (see ``escrow.py``); this module
is only the runtime holder, never the durable store, and never logs material."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Key:
    id: str
    material: bytes  # 32 bytes -> AES-256


def _mint() -> Key:
    """A fresh random key; its id is derived from the material so it is stable
    and unique per key without any external counter."""
    material = os.urandom(32)
    return Key(id=hashlib.sha256(b"id:" + material).hexdigest()[:12], material=material)


@runtime_checkable
class KeyProvider(Protocol):
    def current_key(self) -> Key: ...
    def key(self, key_id: str) -> Key: ...
    def rotate(self) -> Key: ...


class StubKeyProvider:
    """Dev-only: a single key derived from a passphrase. NOT for production —
    no rotation, no escrow, no recovery. ``rotate`` refuses loudly rather than
    pretend (no silent fallback); ``key`` resolves only its one version."""

    def __init__(self, passphrase: str):
        self._material = hashlib.sha256(passphrase.encode("utf-8")).digest()

    def current_key(self) -> Key:
        key_id = hashlib.sha256(b"id:" + self._material).hexdigest()[:12]
        return Key(id=key_id, material=self._material)

    def key(self, key_id: str) -> Key:
        current = self.current_key()
        if key_id != current.id:
            raise KeyError(f"unknown key_id: {key_id}")
        return current

    def rotate(self) -> Key:
        raise NotImplementedError(
            "StubKeyProvider is single-key dev tooling; use InMemoryKeyProvider "
            "for rotation."
        )


class InMemoryKeyProvider:
    """Versioned keys held in memory. ``rotate`` mints a new active key while
    every prior version stays resolvable by ``key_id``. Recovered keys (from
    escrow) are re-admitted via ``add`` so they can decrypt their entries."""

    def __init__(self, initial: Key | None = None):
        first = initial or _mint()
        self._keys: dict[str, Key] = {first.id: first}
        self._current = first.id

    def current_key(self) -> Key:
        return self._keys[self._current]

    def key(self, key_id: str) -> Key:
        try:
            return self._keys[key_id]
        except KeyError:
            raise KeyError(f"unknown key_id: {key_id}") from None

    def rotate(self) -> Key:
        new = _mint()
        self._keys[new.id] = new
        self._current = new.id
        return new

    def add(self, key: Key) -> None:
        """Re-admit a key version (e.g. one recovered from escrow)."""
        self._keys[key.id] = key
