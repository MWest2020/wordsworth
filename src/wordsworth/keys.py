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


# Keys are scoped so each PII type can have its own key: possessing a type's key
# reveals only that type (the lever a grant shares or revokes). Callers that do
# not care about types use the single default scope and see the original
# single-key behaviour. ``key(key_id)`` resolves any version regardless of scope,
# so a stored mapping still decrypts by its recorded ``key_id`` alone.
DEFAULT_SCOPE = "_global"


@runtime_checkable
class KeyProvider(Protocol):
    def current_key(self, scope: str = DEFAULT_SCOPE) -> Key: ...
    def key(self, key_id: str) -> Key: ...
    def rotate(self, scope: str = DEFAULT_SCOPE) -> Key: ...


class StubKeyProvider:
    """Dev-only: a single key derived from a passphrase, the same across every
    scope. NOT for production — no rotation, no escrow, no recovery. ``rotate``
    refuses loudly rather than pretend (no silent fallback)."""

    def __init__(self, passphrase: str):
        self._material = hashlib.sha256(passphrase.encode("utf-8")).digest()

    def current_key(self, scope: str = DEFAULT_SCOPE) -> Key:
        key_id = hashlib.sha256(b"id:" + self._material).hexdigest()[:12]
        return Key(id=key_id, material=self._material)

    def key(self, key_id: str) -> Key:
        current = self.current_key()
        if key_id != current.id:
            raise KeyError(f"unknown key_id: {key_id}")
        return current

    def rotate(self, scope: str = DEFAULT_SCOPE) -> Key:
        raise NotImplementedError(
            "StubKeyProvider is single-key dev tooling; use InMemoryKeyProvider "
            "for rotation."
        )


class InMemoryKeyProvider:
    """Versioned keys held in memory, per scope. Each scope has its own active
    key and rotation history; an unseen scope mints its key lazily on first use.
    ``rotate(scope)`` mints a new active key for that scope while every prior
    version (any scope) stays resolvable by ``key_id``. Recovered keys (from
    escrow) are re-admitted via ``add`` so they can decrypt their entries."""

    def __init__(self, initial: Key | None = None):
        first = initial or _mint()
        self._keys: dict[str, Key] = {first.id: first}
        self._current: dict[str, str] = {DEFAULT_SCOPE: first.id}

    def current_key(self, scope: str = DEFAULT_SCOPE) -> Key:
        if scope not in self._current:
            fresh = _mint()
            self._keys[fresh.id] = fresh
            self._current[scope] = fresh.id
        return self._keys[self._current[scope]]

    def key(self, key_id: str) -> Key:
        try:
            return self._keys[key_id]
        except KeyError:
            raise KeyError(f"unknown key_id: {key_id}") from None

    def rotate(self, scope: str = DEFAULT_SCOPE) -> Key:
        self.current_key(scope)  # ensure the scope exists before rotating it
        new = _mint()
        self._keys[new.id] = new
        self._current[scope] = new.id
        return new

    def add(self, key: Key) -> None:
        """Re-admit a key version (e.g. one recovered from escrow)."""
        self._keys[key.id] = key
