# SPDX-License-Identifier: MIT
"""The seam (ADR-0008): the only two functions that read or write an original.
Plain code keeps passing a `store` around without caring which kind it holds --
`read_original`/`write_original` pick the sealed path when it is an
`OriginalsStore`, and fall back to the plain `ObjectStore` methods otherwise.
Nothing calls these yet: the read sites move in `originals-ingest-readers`,
ingest in `originals-ingest-write`."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from .object_store import ObjectStore
from .originals_store import OriginalsStore, PutResult


def read_original(session: Session, store: ObjectStore, object_key: str) -> bytes:
    """The original's bytes. `get_original` when `store` is an
    `OriginalsStore`, else the plain `store.get` -- which still raises
    `SealedObjectError` on a sealed object: fail closed, no fallback."""
    if isinstance(store, OriginalsStore):
        return store.get_original(session, object_key)
    return store.get(object_key)


def write_original(session: Session, store: ObjectStore, document_id: UUID,
                   object_key: str, data: bytes) -> PutResult:
    """Write an original. `put_original` when `store` is an `OriginalsStore`
    (its five idempotency rules apply). Otherwise a plain `put`, reported as
    `PutResult.WROTE` when the object was absent before and `UNCHANGED` when
    it already existed -- matching `put_original`'s return type."""
    if isinstance(store, OriginalsStore):
        return store.put_original(session, document_id, object_key, data)
    existed = store.exists(object_key)
    store.put(object_key, data)
    return PutResult.UNCHANGED if existed else PutResult.WROTE
