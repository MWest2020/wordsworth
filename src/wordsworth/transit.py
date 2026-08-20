"""OpenBao Transit envelope seam + durable key-vault store (ADR-0002).

Data keys are wrapped by a KEK that never leaves OpenBao (Transit engine), and
only the wrapped blob is persisted in ``key_vault``. ``FakeTransit`` is the test
double (an in-memory reversible envelope); ``OpenBaoTransit`` is the real client,
live-verified against a running OpenBao in the deploy step — NOT in CI."""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import KeyVaultRecord


@runtime_checkable
class Transit(Protocol):
    """Envelope KEK: wrap/unwrap data-key material. The KEK stays in the backend;
    only wrapped bytes are ever persisted."""

    def wrap(self, plaintext: bytes) -> bytes: ...
    def unwrap(self, ciphertext: bytes) -> bytes: ...


class FakeTransit:
    """In-memory reversible envelope for tests — AES-GCM under a fixed KEK, with a
    fresh nonce per wrap so the wrapped output differs from the plaintext. NOT a
    KMS and NOT sovereign; never use outside tests."""

    _KEK = bytes(range(32))  # fixed, non-zero test KEK

    def __init__(self, kek: bytes | None = None):
        self._kek = kek or self._KEK

    def wrap(self, plaintext: bytes) -> bytes:
        nonce = os.urandom(12)
        return nonce + AESGCM(self._kek).encrypt(nonce, plaintext, b"transit")

    def unwrap(self, ciphertext: bytes) -> bytes:
        nonce, body = ciphertext[:12], ciphertext[12:]
        return AESGCM(self._kek).decrypt(nonce, body, b"transit")


class OpenBaoTransit:
    """Real OpenBao/Vault Transit client. ``wrap`` POSTs base64 plaintext to
    ``/v1/transit/encrypt/{kek}`` and stores the returned ``vault:v1:…`` ciphertext
    token; ``unwrap`` POSTs it to ``/v1/transit/decrypt/{kek}``. The KEK never
    leaves the server. Auth is a scoped token (never root). LIVE-VERIFIED in the
    OpenBao deploy step — CI exercises only request shaping via monkeypatch."""

    def __init__(self, url: str, token: str, kek: str, timeout: float = 10.0):
        self._url = url.rstrip("/")
        self._token = token
        self._kek = kek
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"X-Vault-Token": self._token}

    def wrap(self, plaintext: bytes) -> bytes:
        resp = httpx.post(
            f"{self._url}/v1/transit/encrypt/{self._kek}",
            headers=self._headers(),
            json={"plaintext": base64.b64encode(plaintext).decode("ascii")},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()["data"]["ciphertext"].encode("utf-8")

    def unwrap(self, ciphertext: bytes) -> bytes:
        resp = httpx.post(
            f"{self._url}/v1/transit/decrypt/{self._kek}",
            headers=self._headers(),
            json={"ciphertext": ciphertext.decode("utf-8")},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return base64.b64decode(resp.json()["data"]["plaintext"])


@dataclass(frozen=True)
class VaultEntry:
    key_id: str
    scope: str
    wrapped_material: bytes
    status: str


@runtime_checkable
class KeyVaultStore(Protocol):
    def put(self, key_id: str, scope: str, wrapped_material: bytes,
            status: str = "active") -> None: ...
    def get(self, key_id: str) -> VaultEntry | None: ...
    def active_for(self, scope: str) -> VaultEntry | None: ...
    def set_status(self, key_id: str, status: str) -> None: ...


class PostgresKeyVaultStore:
    """Durable ``key_vault`` store in PostgreSQL. The caller owns the session
    transaction (commit/rollback)."""

    def __init__(self, session: Session):
        self._session = session

    def put(self, key_id: str, scope: str, wrapped_material: bytes,
            status: str = "active") -> None:
        if self._session.get(KeyVaultRecord, key_id) is not None:
            return
        self._session.add(KeyVaultRecord(
            key_id=key_id, scope=scope, wrapped_material=wrapped_material,
            status=status, created_at=datetime.now(timezone.utc),
        ))
        self._session.flush()

    def get(self, key_id: str) -> VaultEntry | None:
        row = self._session.get(KeyVaultRecord, key_id)
        if row is None:
            return None
        return VaultEntry(row.key_id, row.scope, row.wrapped_material, row.status)

    def active_for(self, scope: str) -> VaultEntry | None:
        row = self._session.execute(
            select(KeyVaultRecord)
            .where(KeyVaultRecord.scope == scope, KeyVaultRecord.status == "active")
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None
        return VaultEntry(row.key_id, row.scope, row.wrapped_material, row.status)

    def set_status(self, key_id: str, status: str) -> None:
        row = self._session.get(KeyVaultRecord, key_id)
        if row is None:
            raise KeyError(f"unknown key_id: {key_id}")
        row.status = status
        self._session.flush()


class InMemoryKeyVaultStore:
    """Dict-backed ``KeyVaultStore`` test double."""

    def __init__(self) -> None:
        self._d: dict[str, VaultEntry] = {}

    def put(self, key_id: str, scope: str, wrapped_material: bytes,
            status: str = "active") -> None:
        self._d.setdefault(key_id, VaultEntry(key_id, scope, wrapped_material, status))

    def get(self, key_id: str) -> VaultEntry | None:
        return self._d.get(key_id)

    def active_for(self, scope: str) -> VaultEntry | None:
        for entry in self._d.values():
            if entry.scope == scope and entry.status == "active":
                return entry
        return None

    def set_status(self, key_id: str, status: str) -> None:
        entry = self._d.get(key_id)
        if entry is None:
            raise KeyError(f"unknown key_id: {key_id}")
        self._d[key_id] = VaultEntry(entry.key_id, entry.scope,
                                     entry.wrapped_material, status)
