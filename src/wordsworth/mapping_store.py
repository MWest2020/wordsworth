"""The separated encrypted mapping store (pseudonym -> ciphertext)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

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
