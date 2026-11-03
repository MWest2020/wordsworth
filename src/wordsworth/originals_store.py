# SPDX-License-Identifier: MIT
"""``OriginalsStore``: the only way an original PDF is written or read
(ADR-0008). ``put_original``'s five rules are design.md §3a; nothing else
writes an original, and nothing calls this module yet -- ingest and the read
sites move in ``originals-ingest-readers`` and ``originals-ingest-write``, and
``originals-ingest-switch`` wires it into the running service."""
from __future__ import annotations

import enum
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import Session

from . import originals_envelope
from .document_keys import DocumentKeyRecord, DocumentKeys
from .object_store import ObjectStore, ObjectStoreError, SealedObjectError

if TYPE_CHECKING:
    from .document_keys import DataKey


def _is_sealed(data: bytes) -> bool:
    return data[:len(originals_envelope.HEADER_MAGIC)] == originals_envelope.HEADER_MAGIC


class PutResult(enum.Enum):
    """``put_original``'s outcome. Not a bool: a bool cannot distinguish
    "legacy, left alone" from "wrote", and a truthy result would let
    ``if wrote: delete(key)`` delete a live legacy object after a failed
    commit -- the only readable copy of a document. ``__bool__`` raises, so
    that mistake fails the first time it runs instead of staying quiet."""

    WROTE = "wrote"
    UNCHANGED = "unchanged"
    LEGACY = "legacy"

    def __bool__(self) -> bool:
        raise TypeError(
            "PutResult has no truth value; compare with `is PutResult.WROTE`")


class OriginalsStore:
    """Composes an ``ObjectStore`` and a ``DocumentKeys`` store; holds no
    session (design.md §3a "Sessions") -- one process-lifetime instance keeps
    the unwrap cache warm across requests. The underlying store is exposed as
    ``.objects`` for callers that only delete or sweep, never read originals."""

    def __init__(self, objects: ObjectStore, keys: DocumentKeys):
        self.objects = objects
        self._keys = keys

    # --- ObjectStore protocol: an OriginalsStore goes anywhere a plain store
    # goes today (redacted-PDF cache, deletion, audit exports). `get` is the
    # guarded plain read -- it refuses a sealed object exactly as before;
    # callers that want the original open it with `get_original` instead. ---

    def put(self, key: str, data: bytes) -> None:
        self.objects.put(key, data)

    def get(self, key: str) -> bytes:
        return self.objects.get(key)

    def get_raw(self, key: str) -> bytes:
        return self.objects.get_raw(key)

    def iter_objects(self, prefix: str) -> Iterator[tuple[str, datetime]]:
        return self.objects.iter_objects(prefix)

    def exists(self, key: str) -> bool:
        return self.objects.exists(key)

    def delete(self, key: str) -> bool:
        return self.objects.delete(key)

    def _seal_and_write(self, session: Session, row: DocumentKeyRecord,
                        key: "DataKey", object_key: str, data: bytes) -> None:
        sealed = originals_envelope.seal(key.material, key.key_id, object_key, data)
        self.objects.put(object_key, sealed)
        row.sealed_at = datetime.now(timezone.utc)
        session.flush()

    def put_original(self, session: Session, document_id: UUID, object_key: str,
                     data: bytes) -> PutResult:
        row = session.get(DocumentKeyRecord, object_key)
        try:
            stored = self.objects.get_raw(object_key)
        except ObjectStoreError:
            stored = None
        stored_sealed = stored is not None and _is_sealed(stored)

        if row is not None and stored_sealed:
            if originals_envelope.header_key_id(stored) == row.key_id:
                # rule 1: re-ingest of bytes that already open under this row.
                if row.document_id != document_id:
                    row.document_id = document_id
                    session.flush()
                return PutResult.UNCHANGED

        if row is not None and (stored is None or stored_sealed):
            # rule 2: object missing, or sealed under a stale key_id (a
            # rolled-back write) -- reseal with the row's own key, never a
            # second one. Nothing readable is overwritten.
            key = self._keys.unwrap(session, object_key)
            self._seal_and_write(session, row, key, object_key, data)
            return PutResult.WROTE

        if row is None and (stored is None or stored_sealed):
            # rule 3: no row, object missing or an orphan -- mint, then write.
            from .pipeline import document_domain
            domain = document_domain(session, document_id)
            key = self._keys.mint(session, document_id, object_key, domain)
            fresh_row = session.get(DocumentKeyRecord, object_key)
            self._seal_and_write(session, fresh_row, key, object_key, data)
            return PutResult.WROTE

        # The stored object is legacy plaintext (no sealed header).
        if row is None or row.sealed_at is None:
            # rule 4: never overwrite the only readable copy of a document;
            # that is originals-encrypt-existing's job, done after it verifies.
            return PutResult.LEGACY

        # rule 5: the row says sealed, the object says otherwise -- a
        # downgrade. Repairing it by guess would be a silent fallback.
        raise SealedObjectError(
            f"{object_key!r} has a sealed key row but no sealed header")

    def get_original(self, session: Session, object_key: str) -> bytes:
        row = session.get(DocumentKeyRecord, object_key)
        stored = self.objects.get_raw(object_key)
        if not _is_sealed(stored):
            if row is not None and row.sealed_at is not None:
                raise SealedObjectError(
                    f"{object_key!r} is recorded as sealed but carries no header")
            return stored  # legacy plaintext, or a row not yet sealed
        key = self._keys.unwrap(session, object_key)
        return originals_envelope.open(key.material, key.key_id, object_key, stored)
