"""The service's own document-key store (design.md "The document-key store
is the service's own"): ``mint``, ``unwrap``, ``evict`` and the bounded
unwrap cache, reimplemented over the service's own ``DocumentKeyRecord`` --
never ``wordsworth.document_keys.DocumentKeys``, which inserts and selects
wordsworth's own model on wordsworth's session (design.md rejects that
reuse: because the service copied the table's name and columns, that store
would silently work against the service's session, exactly what skeleton
rule 3 forbids).

``unwrap`` classifies a Transit failure into ``KeyBackendUnavailable`` (no
answer about the ciphertext: a connect/timeout error, or an HTTP 5xx) or
``KeyDoesNotUnwrap`` (the backend answered and refused: an HTTP 4xx, or
``cryptography``'s ``InvalidTag`` from ``FakeTransit``) -- never by reading
the exception's message text. Anything else propagates as a 500."""
from __future__ import annotations

import hashlib
import os
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import httpx
from cryptography.exceptions import InvalidTag
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from wordsworth.transit import Transit

from .config import settings
from .models import DocumentKeyRecord


class KeyBackendUnavailable(Exception):
    """Transit did not get an answer about the ciphertext: a connect or
    timeout error, or an HTTP 5xx (OpenBao sealed or down)."""


class KeyDoesNotUnwrap(Exception):
    """Transit answered and refused the ciphertext: an HTTP 4xx, or
    ``cryptography``'s ``InvalidTag`` from ``FakeTransit``."""


def kek_for(domain: str) -> str:
    """The Transit KEK name for a domain: the per-domain override if
    configured, else the shared default."""
    return settings.originals_kek_by_domain.get(domain, settings.originals_kek)


@dataclass(frozen=True)
class DataKey:
    key_id: str  # 12 hex characters, matches originals_envelope's key_id slot
    material: bytes  # 32 bytes, AES-256 -- never persisted in clear


def _mint_dek() -> DataKey:
    material = os.urandom(32)
    key_id = hashlib.sha256(b"id:" + material).hexdigest()[:12]
    return DataKey(key_id, material)


def _classify(exc: Exception) -> Exception:
    """Map a Transit failure to ``KeyBackendUnavailable`` or
    ``KeyDoesNotUnwrap`` (design.md's split), or return ``exc`` unchanged
    when it is neither -- the caller re-raises that case as-is, a 500."""
    if isinstance(exc, httpx.HTTPStatusError):
        if exc.response.status_code >= 500:
            return KeyBackendUnavailable(str(exc))
        return KeyDoesNotUnwrap(str(exc))
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return KeyBackendUnavailable(str(exc))
    if isinstance(exc, InvalidTag):
        return KeyDoesNotUnwrap("wrapped material does not authenticate")
    return exc


class DocumentKeys:
    """Mint and unwrap data keys for sealed objects. ``transit_for`` is a
    factory (``str -> Transit``), never one bound ``Transit`` -- the KEK name
    varies per row (``row.kek_ref``) and per domain (``kek_for``). Holds no
    session -- the unwrap cache is the only state, process-lifetime by
    construction (one instance per process)."""

    def __init__(self, transit_for: Callable[[str], Transit], *,
                cache_size: int | None = None, cache_ttl: float | None = None,
                clock: Callable[[], float] = time.monotonic):
        self._transit_for = transit_for
        self._cache_size = (cache_size if cache_size is not None
                            else settings.document_key_cache_size)
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
            classified = _classify(exc)
            if classified is exc:
                raise
            raise classified from exc
        key = DataKey(row.key_id, material)
        self._cache_put(row.object_key, key)
        return key

    def mint(self, session: Session, document_id: uuid.UUID, object_key: str,
             domain: str) -> DataKey:
        """A fresh data key for ``object_key``, wrapped under ``kek_for(domain)``
        and inserted in a savepoint. On a concurrent mint for the same object
        key, adopts the winner's key instead of ending with two rows."""
        kek_name = kek_for(domain)
        fresh = _mint_dek()
        wrapped = self._transit_for(kek_name).wrap(fresh.material)
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
        rows were destroyed). Correctness does not depend on it -- ``unwrap``
        checks the row on every call."""
        for object_key in object_keys:
            self._cache.pop(object_key, None)

    def unwrap(self, session: Session, object_key: str) -> DataKey:
        """The data key for ``object_key``, from the cache or unwrapped via
        ``transit_for(row.kek_ref)`` -- never the current setting, so a
        changed KEK setting affects only new objects. Every call re-reads the
        key row (crypto-shred): a cached key is used only while a row with
        the same ``key_id`` still exists."""
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
            raise KeyDoesNotUnwrap(f"no key row for {object_key!r}")
        return self._unwrap_row(row)
