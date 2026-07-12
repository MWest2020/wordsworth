"""The separated encrypted mapping store (pseudonym -> ciphertext)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .crypto import decrypt, encrypt
from .keys import KeyProvider
from .models import PiiMapping


@dataclass
class Mapping:
    pseudonym: str
    ciphertext: bytes
    nonce: bytes
    key_id: str


@runtime_checkable
class MappingStore(Protocol):
    def put(self, pseudonym: str, ciphertext: bytes, nonce: bytes, key_id: str) -> None: ...
    def get(self, pseudonym: str) -> Mapping | None: ...
    def reencrypt(self, old_id: str, new_id: str, key_provider: KeyProvider) -> int: ...


class PostgresMappingStore:
    """Separated store in PostgreSQL. `put` is idempotent: one row per pseudonym."""

    def __init__(self, session: Session):
        self._session = session

    def put(self, pseudonym: str, ciphertext: bytes, nonce: bytes, key_id: str) -> None:
        if self._session.get(PiiMapping, pseudonym) is not None:
            return
        self._session.add(
            PiiMapping(
                pseudonym=pseudonym,
                ciphertext=ciphertext,
                nonce=nonce,
                key_id=key_id,
                created_at=datetime.now(timezone.utc),
            )
        )
        self._session.flush()

    def get(self, pseudonym: str) -> Mapping | None:
        row = self._session.get(PiiMapping, pseudonym)
        if row is None:
            return None
        return Mapping(row.pseudonym, row.ciphertext, row.nonce, row.key_id)

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
