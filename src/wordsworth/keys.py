"""Key provider seam. The PoC ships a dev stub only — real lifecycle (rotation,
escrow, recovery) is MVP work behind the same protocol."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Key:
    id: str
    material: bytes  # 32 bytes -> AES-256


@runtime_checkable
class KeyProvider(Protocol):
    def current_key(self) -> Key: ...


class StubKeyProvider:
    """Dev-only: a single key derived from a passphrase. NOT for production —
    no rotation, no escrow, no recovery."""

    def __init__(self, passphrase: str):
        self._material = hashlib.sha256(passphrase.encode("utf-8")).digest()

    def current_key(self) -> Key:
        key_id = hashlib.sha256(b"id:" + self._material).hexdigest()[:12]
        return Key(id=key_id, material=self._material)
