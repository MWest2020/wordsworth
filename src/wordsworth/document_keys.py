# SPDX-License-Identifier: MIT
"""The ``document_keys`` table and its store (ADR-0008): one row per sealed
**object**, holding the data key wrapped by a KEK (OpenBao Transit) -- never
in clear. Keyed by ``object_key`` (not document id) because one document can
have two sealed objects (a scan and its OCR'd PDF, ``originals-ocr-sealed``).

The model lives here, outside ``models.py``: a model class in a module nobody
imports is absent from ``Base.metadata``, so ``db.py`` imports this module
next to ``models`` to keep the table reachable from ``init_schema``.

``OriginalsKeyUnavailable`` and ``kek_name_for`` live here too, next to the
model, ``mint``, ``unwrap`` and the cache; ``SealedObjectError`` stays in
``object_store.py`` so that lower layer never imports this module or
``originals_envelope``."""
from __future__ import annotations

import hashlib
import os
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .config import settings
from .models import Base
from .transit import Transit


class OriginalsKeyUnavailable(Exception):
    """Raised when a data key cannot be minted or unwrapped: the key service
    is unreachable or refuses, the wrapped material is tampered, or the row's
    KEK does not match the one that wrapped it. Never carries key material."""


def kek_name_for(domain: str) -> str:
    """The Transit KEK name for a pseudonymisation domain (design.md "KEK per
    domain"): the per-domain override if configured, else the shared default.
    One domain per organisation makes a KEK-per-organisation a config change."""
    return settings.originals_kek_by_domain.get(domain, settings.originals_kek)


@dataclass(frozen=True)
class DataKey:
    key_id: str  # 12 hex characters, matches originals_envelope's key_id slot
    material: bytes  # 32 bytes, AES-256 -- never persisted in clear


def _mint_dek() -> DataKey:
    material = os.urandom(32)
    key_id = hashlib.sha256(b"id:" + material).hexdigest()[:12]
    return DataKey(key_id, material)


class DocumentKeyRecord(Base):
    """One row per sealed object (design.md §5). ``sealed_at`` NULL means the
    key is minted but the object under it is not (yet) sealed -- the state
    ``originals-encrypt-existing`` commits on purpose before it replaces a
    plaintext object; the downgrade guard applies only once it is set."""

    __tablename__ = "document_keys"

    object_key: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id"), nullable=False, index=True)
    key_id: Mapped[str] = mapped_column(String, nullable=False)
    kek_ref: Mapped[str] = mapped_column(String, nullable=False)
    wrapped_material: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DocumentKeys:
    """Mint and unwrap data keys for sealed objects. ``transit_for`` is a
    factory (``str -> Transit``), not one bound ``Transit``, because
    ``OpenBaoTransit`` binds its KEK name at construction (design.md "KEK per
    domain"). Holds no session -- the unwrap cache is the only state, and it
    is process-lifetime by construction (one instance per process)."""

    def __init__(self, transit_for: Callable[[str], Transit], *,
                 cache_size: int | None = None, cache_ttl: float | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self._transit_for = transit_for
        self._cache_size = cache_size if cache_size is not None else settings.document_key_cache_size
        self._cache_ttl = cache_ttl if cache_ttl is not None else settings.key_cache_ttl
        self._clock = clock
        self._cache: OrderedDict[str, tuple[DataKey, float]] = OrderedDict()

    def _cache_get(self, object_key: str) -> DataKey | None:
        hit = self._cache.get(object_key)
        if hit is None:
            return None
        key, expiry = hit
        if expiry <= self._clock():
            del self._cache[object_key]
            return None
        self._cache.move_to_end(object_key)
        return key

    def _cache_put(self, object_key: str, key: DataKey) -> None:
        self._cache[object_key] = (key, self._clock() + self._cache_ttl)
        self._cache.move_to_end(object_key)
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    def _unwrap_row(self, row: DocumentKeyRecord) -> DataKey:
        try:
            material = self._transit_for(row.kek_ref).unwrap(row.wrapped_material)
        except Exception as exc:
            raise OriginalsKeyUnavailable(
                f"key unavailable for {row.object_key!r}") from exc
        key = DataKey(row.key_id, material)
        self._cache_put(row.object_key, key)
        return key

    def mint(self, session: Session, document_id: uuid.UUID, object_key: str,
             domain: str) -> DataKey:
        """A fresh data key for ``object_key``, wrapped under the KEK for
        ``domain`` and inserted in a savepoint. On a concurrent mint for the
        same object key, adopts the winner's key instead of ending with two
        rows -- the pattern ``register_live`` uses for documents. Raises
        ``OriginalsKeyUnavailable`` before anything is written if the key
        service is unreachable or refuses."""
        kek_name = kek_name_for(domain)
        fresh = _mint_dek()
        try:
            wrapped = self._transit_for(kek_name).wrap(fresh.material)
        except Exception as exc:
            raise OriginalsKeyUnavailable(
                f"key service unavailable for {object_key!r}") from exc
        try:
            with session.begin_nested():
                session.add(DocumentKeyRecord(
                    object_key=object_key, document_id=document_id, key_id=fresh.key_id,
                    kek_ref=kek_name, wrapped_material=wrapped,
                    created_at=datetime.now(timezone.utc), sealed_at=None))
                session.flush()
        except IntegrityError:
            row = session.get(DocumentKeyRecord, object_key)
            if row is None:
                raise
            return self._unwrap_row(row)
        self._cache_put(object_key, fresh)
        return fresh

    def evict(self, object_keys) -> None:
        """Drop these entries from this process's unwrap cache (after their
        rows were destroyed). Touches nothing else; correctness does not
        depend on it -- ``unwrap`` checks the row on every call."""
        for object_key in object_keys:
            self._cache.pop(object_key, None)

    def unwrap(self, session: Session, object_key: str) -> DataKey:
        """The data key for ``object_key``, from the cache or unwrapped via
        ``transit_for(row.kek_ref)`` -- never the current setting, so a
        changed KEK setting affects only new objects.

        Every call reads the key row from the database (crypto-shred): a
        cached key is used only while a row with the same ``key_id`` exists,
        so a key destroyed by another process (another replica) is never
        served from this cache, and one destroyed and minted again under the
        same object key is not served from the old entry. Both reads are
        ``select`` statements, never ``session.get``, which could answer from
        the identity map after another transaction deleted the row. This
        relies on READ COMMITTED (each statement sees what was committed
        before it started); ``db.py`` sets no other level."""
        cached = self._cache_get(object_key)
        if cached is not None:
            key_id = session.execute(
                select(DocumentKeyRecord.key_id)
                .where(DocumentKeyRecord.object_key == object_key)
            ).scalar_one_or_none()
            if key_id == cached.key_id:
                return cached
            self._cache.pop(object_key, None)
        row = session.execute(
            select(DocumentKeyRecord)
            .where(DocumentKeyRecord.object_key == object_key)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if row is None:
            raise OriginalsKeyUnavailable(f"no key row for {object_key!r}")
        return self._unwrap_row(row)
