# SPDX-License-Identifier: MIT
"""The seam (ADR-0008, `originals-ingest-seam`): the only way code reads or
writes an original. `read_original` and `write_original` branch on whether
`store` is an `OriginalsStore` (seal/open) or a plain `ObjectStore` (plain
read/write) -- callers never branch on that themselves."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from .object_store import ObjectStore
from .originals_store import OriginalsStore, PutResult


def read_original(session: Session, store: ObjectStore, object_key: str) -> bytes:
    """`OriginalsStore.get_original` (opens a sealed object) for an originals
    store, else the plain `store.get` -- which keeps refusing a sealed object
    (`SealedObjectError`): no fallback to ciphertext-as-plaintext."""
    if isinstance(store, OriginalsStore):
        return store.get_original(session, object_key)
    return store.get(object_key)


def write_original(session: Session, store: ObjectStore, document_id: UUID,
                   object_key: str, data: bytes) -> PutResult:
    """`OriginalsStore.put_original` (seals) for an originals store, else a
    plain `store.put`, reported as `PutResult.WROTE` when `object_key` was
    absent before and `PutResult.UNCHANGED` when it already existed."""
    if isinstance(store, OriginalsStore):
        return store.put_original(session, document_id, object_key, data)
    existed = store.exists(object_key)
    store.put(object_key, data)
    return PutResult.UNCHANGED if existed else PutResult.WROTE


def originals_from_config(store: ObjectStore) -> OriginalsStore:
    """`OriginalsStore` over `store`, with `DocumentKeys` wired to the same
    OpenBao Transit config `serve.build_app` uses (originals-ingest-switch) --
    the CLIs' entry point onto the seam, so neither builds a transit itself."""
    from .config import settings
    from .document_keys import DocumentKeys
    from .transit import transit_factory

    transit_for = transit_factory(settings.openbao_url, settings.openbao_token)
    return OriginalsStore(store, DocumentKeys(transit_for))
