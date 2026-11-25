"""The separated encrypted mapping store (pseudonym -> ciphertext)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from .crypto import decrypt, encrypt
from .keys import KeyProvider
from .mapping_buffer import PENDING
from .models import PiiMapping


@dataclass
class Mapping:
    pseudonym: str
    ciphertext: bytes
    nonce: bytes
    key_id: str
    norm_version: str | None = None  # normalisation profile; None = legacy (raw)


@runtime_checkable
class MappingStore(Protocol):
    def put(self, pseudonym: str, ciphertext: bytes, nonce: bytes, key_id: str,
            norm_version: str | None = None) -> None: ...
    def get(self, pseudonym: str) -> Mapping | None: ...
    def reencrypt(self, old_id: str, new_id: str, key_provider: KeyProvider) -> int: ...


class PostgresMappingStore:
    """Separated store in PostgreSQL. `put` is idempotent: one row per pseudonym.

    `put` only buffers the row on the session (`mapping_buffer`);
    `mapping_buffer.write_pending` stores it under the audit chain lock.
    `process` and `reanonymize` write through `pseudonym_registry.link`, any
    other caller calls `write_pending` itself, before its audit record. A
    commit with rows still buffered raises `UnwrittenMappings`."""

    def __init__(self, session: Session):
        self._session = session

    def put(self, pseudonym: str, ciphertext: bytes, nonce: bytes, key_id: str,
            norm_version: str | None = None) -> None:
        # The first `put` of a pseudonym wins (both encrypt the same value).
        # Inside a transaction, so the buffer ends with it (the listeners in
        # `mapping_buffer`); begins one if none is open, no statement is sent.
        self._session.connection()
        self._session.info.setdefault(PENDING, {}).setdefault(pseudonym, dict(
            pseudonym=pseudonym, ciphertext=ciphertext, nonce=nonce,
            key_id=key_id, norm_version=norm_version,
            created_at=datetime.now(timezone.utc)))

    def get(self, pseudonym: str) -> Mapping | None:
        row = self._session.get(PiiMapping, pseudonym)
        if row is not None:
            return Mapping(row.pseudonym, row.ciphertext, row.nonce, row.key_id,
                           row.norm_version)
        p = self._session.info.get(PENDING, {}).get(pseudonym)
        return None if p is None else Mapping(
            pseudonym, p["ciphertext"], p["nonce"], p["key_id"], p["norm_version"])

    def reencrypt(self, old_id: str, new_id: str, key_provider: KeyProvider) -> int:
        """Re-encrypt every entry under ``old_id`` onto ``new_id`` and return the
        count. Decrypts with the old key, re-encrypts with the new (fresh nonce),
        and updates the row's ``key_id`` in place. Only ``pii_mappings`` is
        touched — documents and the index are never modified. This is the payoff
        of the separated store over in-document PII: rotation is cheap."""
        old = key_provider.key(old_id)
        new = key_provider.key(new_id)
        rows = self._session.execute(
            select(PiiMapping).where(PiiMapping.key_id == old_id)
        ).scalars().all()
        for row in rows:
            plaintext = decrypt(old.material, row.ciphertext, row.nonce)
            row.ciphertext, row.nonce = encrypt(new.material, plaintext)
            row.key_id = new_id
        self._session.flush()
        return len(rows)


def remove_orphans(session: Session, pseudonyms: list[str]) -> None:
    """Delete these mapping rows, locked FOR UPDATE in pseudonym order first.
    The caller holds the audit chain lock and has checked, under it, that no
    other document is linked to them (`deletion_mappings`)."""
    if not pseudonyms:
        return
    session.execute(select(PiiMapping.pseudonym)
                    .where(PiiMapping.pseudonym.in_(pseudonyms))
                    .order_by(PiiMapping.pseudonym).with_for_update())
    session.execute(sa_delete(PiiMapping)
                    .where(PiiMapping.pseudonym.in_(pseudonyms))
                    .execution_options(synchronize_session="fetch"))


class InMemoryMappingStore:
    """Dict-backed ``MappingStore`` — a test double and a non-DB wiring option,
    mirroring ``InMemoryIndex``. ``put`` is idempotent: one entry per pseudonym."""

    def __init__(self) -> None:
        self._d: dict[str, Mapping] = {}

    def put(self, pseudonym: str, ciphertext: bytes, nonce: bytes, key_id: str,
            norm_version: str | None = None) -> None:
        self._d.setdefault(
            pseudonym, Mapping(pseudonym, ciphertext, nonce, key_id, norm_version))

    def get(self, pseudonym: str) -> Mapping | None:
        return self._d.get(pseudonym)

    def reencrypt(self, old_id: str, new_id: str, key_provider: KeyProvider) -> int:
        old = key_provider.key(old_id)
        new = key_provider.key(new_id)
        n = 0
        for pseudonym, m in list(self._d.items()):
            if m.key_id != old_id:
                continue
            plaintext = decrypt(old.material, m.ciphertext, m.nonce)
            ciphertext, nonce = encrypt(new.material, plaintext)
            self._d[pseudonym] = Mapping(pseudonym, ciphertext, nonce, new_id,
                                         m.norm_version)
            n += 1
        return n
