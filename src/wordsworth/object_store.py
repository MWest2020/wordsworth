"""Object storage seam. Document bytes live in S3-compatible storage — SeaweedFS
for the PoC, Ceph RGW as the sovereign target. MinIO is banned (open-source
edition deprecated April 2026); the S3 API is the contract so the backend is a
config change, not a code change.

Credentials and endpoint come from config, sourced via SOPS+age or OpenBao —
never hardcoded, client-side, or commercial. A missing/failed object is a HARD
error (ObjectStoreError), never a silent empty-bytes fallback."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


from .object_store_base import (  # noqa: F401 -- re-exported, the public names
    _SEALED_MAGIC,
    ObjectMissingError,
    ObjectStoreError,
    SealedObjectError,
    _is_sealed,
)


@runtime_checkable
class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    #: The plain read: refuses a sealed object (`SealedObjectError`), so
    #: ciphertext is never handed back as if it were the original.
    def get(self, key: str) -> bytes: ...
    #: The unguarded read -- sealed bytes or a legacy plain object, as stored.
    #: Exactly three callers need it: `OriginalsStore.get_original`,
    #: `put_original`'s header inspection, and `wordsworth-sealed-orphans`.
    def get_raw(self, key: str) -> bytes: ...
    #: Every (key, last_modified) under `prefix`, for the orphan sweep.
    def iter_objects(self, prefix: str) -> Iterator[tuple[str, datetime]]: ...
    #: The first ``n`` bytes only (an S3 ranged GET): enough to classify an
    #: object by its header without downloading it.
    def get_head(self, key: str, n: int) -> bytes: ...
    #: The object's size in bytes (an S3 HEAD), or None when it does not exist.
    def size(self, key: str) -> int | None: ...
    def exists(self, key: str) -> bool: ...
    #: Remove one object. Returns whether it was there -- a missing key is not
    #: an error to delete (document-deletion): a rerun after a partial failure
    #: finishes the work, and removing what is already gone is a no-op.
    def delete(self, key: str) -> bool: ...


class InMemoryObjectStore:
    """dict-backed test double. The pipeline never depends on a live bucket in
    tests, and a missing key raises the same clear error as the S3 driver."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}
        self._modified: dict[str, datetime] = {}

    def put(self, key: str, data: bytes) -> None:
        self._data[key] = bytes(data)
        self._modified[key] = datetime.now(timezone.utc)

    def get_raw(self, key: str) -> bytes:
        try:
            return self._data[key]
        except KeyError as exc:
            raise ObjectMissingError(f"get {key!r} failed: no such object") from exc

    def get_head(self, key: str, n: int) -> bytes:
        # Not through get_raw: like S3's ranged GET, a separate read path.
        if key not in self._data:
            raise ObjectMissingError(f"get-head {key!r} failed: no such object")
        return self._data[key][:max(n, 0)]

    def size(self, key: str) -> int | None:
        data = self._data.get(key)
        return None if data is None else len(data)

    def get(self, key: str) -> bytes:
        data = self.get_raw(key)
        if _is_sealed(data):
            raise SealedObjectError(f"{key!r} is sealed; read it through OriginalsStore")
        return data

    def iter_objects(self, prefix: str) -> Iterator[tuple[str, datetime]]:
        for key, modified in list(self._modified.items()):
            if key.startswith(prefix):
                yield key, modified

    def exists(self, key: str) -> bool:
        return key in self._data

    def delete(self, key: str) -> bool:
        self._modified.pop(key, None)
        return self._data.pop(key, None) is not None


# The S3 driver lives in its own module (the file-size rule); importing it from
# here keeps `from wordsworth.object_store import S3ObjectStore` working. It
# imports only object_store_base, so either module can be imported first.
from .object_store_s3 import S3ObjectStore  # noqa: E402,F401
