"""The service's own mapping store and key vault, over its own models
(``PiiMapping``, ``KeyVaultRecord``, ``KeyServiceBase``) -- never
wordsworth's ``PostgresMappingStore``/``PostgresKeyVaultStore``, which
query wordsworth's own models (design.md "Stores", rejecting that reuse).
Each implements wordsworth's ``MappingStore``/``KeyVaultStore`` protocol
structurally, so ``Pseudonymizer`` and ``DurableKeyProvider`` work over
them unchanged."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from wordsworth.mapping_store import Mapping
from wordsworth.transit import VaultEntry

from .models import KeyVaultRecord, PiiMapping


class PostgresMappingStore:
    """``pii_mappings``, written directly with ``ON CONFLICT DO NOTHING``.
    The caller already holds the registry advisory lock (4781,
    ``known.lock_registry``) for the whole batch before any ``put``, so --
    unlike wordsworth's own store -- there is no separate buffer-then-write
    step: nothing here can race a concurrent writer for the same pseudonym."""

    def __init__(self, session: Session):
        self._session = session

    def put(self, pseudonym: str, ciphertext: bytes, nonce: bytes, key_id: str,
            norm_version: str | None = None) -> None:
        stmt = pg_insert(PiiMapping).values(
            pseudonym=pseudonym, ciphertext=ciphertext, nonce=nonce,
            key_id=key_id, norm_version=norm_version,
            created_at=datetime.now(timezone.utc),
        ).on_conflict_do_nothing(index_elements=["pseudonym"])
        self._session.execute(stmt)

    def get(self, pseudonym: str) -> Mapping | None:
        row = self._session.get(PiiMapping, pseudonym)
        if row is None:
            return None
        return Mapping(row.pseudonym, row.ciphertext, row.nonce, row.key_id,
                       row.norm_version)

    def reencrypt(self, old_id: str, new_id: str, key_provider) -> int:
        raise NotImplementedError(
            "key rotation is out of scope for key-service-pseudonymise")


class PostgresKeyVaultStore:
    """``key_vault``, over the service's own ``KeyVaultRecord``. Mirrors
    wordsworth's ``PostgresKeyVaultStore`` (same idempotent ``put``, same
    partial-unique-index-backed single-active-key-per-scope guarantee),
    over this service's table instead."""

    def __init__(self, session: Session):
        self._session = session

    def put(self, key_id: str, scope: str, wrapped_material: bytes,
            status: str = "active") -> None:
        if self._session.get(KeyVaultRecord, key_id) is not None:
            return
        self._session.add(KeyVaultRecord(
            key_id=key_id, scope=scope, wrapped_material=wrapped_material,
            status=status, created_at=datetime.now(timezone.utc)))
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
