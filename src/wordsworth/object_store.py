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

from .config import settings

#: The sealed-object header's magic bytes (originals_envelope.HEADER_MAGIC),
#: duplicated here on purpose: this is the lower layer, and it must never
#: import originals_envelope to find out whether an object is sealed.
_SEALED_MAGIC = b"WWENC"


class ObjectStoreError(Exception):
    """Raised when an object cannot be stored or fetched (e.g. a missing key)."""


class SealedObjectError(ObjectStoreError):
    """Raised by the plain `get` when the object carries the sealed header:
    ciphertext must never be handed back to a caller expecting a PDF."""


def _is_sealed(data: bytes) -> bool:
    return data[:len(_SEALED_MAGIC)] == _SEALED_MAGIC


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
    def exists(self, key: str) -> bool: ...
    #: Remove one object. Returns whether it was there -- a missing key is not
    #: an error to delete (document-deletion): a rerun after a partial failure
    #: finishes the work, and removing what is already gone is a no-op.
    def delete(self, key: str) -> bool: ...


class S3ObjectStore:
    """boto3 client against any S3-compatible endpoint (SeaweedFS / Ceph RGW)."""

    def __init__(self, client, bucket: str):
        self._client = client
        self._bucket = bucket

    @classmethod
    def from_config(cls) -> "S3ObjectStore":
        # Credentials are read from the secret source (env injected by SOPS+age or
        # OpenBao), never from source code. Absent creds is a hard error, not a
        # silent anonymous fallback.
        if not settings.s3_access_key or not settings.s3_secret_key:
            raise ObjectStoreError(
                "S3 credentials missing; supply via SOPS+age or OpenBao"
            )
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        return cls(client, settings.s3_bucket)

    def put(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def get_raw(self, key: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
        except Exception as exc:  # missing key / network -> hard error, no fallback
            raise ObjectStoreError(f"get {key!r} failed: {exc}") from exc
        return resp["Body"].read()

    def get(self, key: str) -> bytes:
        data = self.get_raw(key)
        if _is_sealed(data):
            raise SealedObjectError(f"{key!r} is sealed; read it through OriginalsStore")
        return data

    def iter_objects(self, prefix: str) -> Iterator[tuple[str, datetime]]:
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                yield obj["Key"], obj["LastModified"]

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                return False
            raise ObjectStoreError(f"head {key!r} failed: {exc}") from exc

    def delete(self, key: str) -> bool:
        if not self.exists(key):
            return False
        self._client.delete_object(Bucket=self._bucket, Key=key)
        return True


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
            raise ObjectStoreError(f"get {key!r} failed: no such object") from exc

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
