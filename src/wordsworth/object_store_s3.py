# SPDX-License-Identifier: MIT
"""The S3 driver of the object-storage seam (`object_store.py`): boto3 against
any S3-compatible endpoint (SeaweedFS for the PoC, Ceph RGW as the target).

**Every read error leaves this module as an ObjectStoreError.** boto3 raises
far more than `ClientError`: a body that breaks off mid-stream surfaces as
urllib3's `ProtocolError`/`IncompleteRead` or botocore's streaming errors, a
slow endpoint as `ReadTimeout`. None of those is an ObjectStoreError, so
before this boundary existed one broken 13 MB GET ended a whole seal dry run
with a traceback (production, 2026-11-15). A read that the store answered
with "no such key" is an `ObjectMissingError`; anything else is a plain
ObjectStoreError -- the object may exist, and nobody may call it missing."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from .config import settings
from .object_store_base import (
    ObjectMissingError,
    ObjectStoreError,
    SealedObjectError,
    _is_sealed,
)

_MISSING_CODES = {"NoSuchKey", "NotFound", "404"}


def _status(exc: Exception) -> tuple[str, int | None]:
    """(error code, HTTP status) of a botocore ClientError; ("", None) else."""
    response = getattr(exc, "response", None)
    if not isinstance(response, dict):
        return "", None
    code = str(response.get("Error", {}).get("Code", ""))
    return code, response.get("ResponseMetadata", {}).get("HTTPStatusCode")


def _is_missing(exc: Exception) -> bool:
    code, status = _status(exc)
    return code in _MISSING_CODES or status == 404


def _read_error(op: str, key: str, exc: Exception) -> ObjectStoreError:
    cls = ObjectMissingError if _is_missing(exc) else ObjectStoreError
    return cls(f"{op} {key!r} failed: {type(exc).__name__}: {exc}")


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
        try:  # the body read inside the try: that is where a stream breaks
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            return resp["Body"].read()
        except Exception as exc:  # missing key / network -> hard error, no fallback
            raise _read_error("get", key, exc) from exc

    def get_head(self, key: str, n: int) -> bytes:
        """The first ``n`` bytes, by a ranged GET. Reads at most ``n`` bytes
        even from an endpoint that ignores the Range header, then closes."""
        if n <= 0:
            return b""
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key,
                                           Range=f"bytes=0-{n - 1}")
            body = resp["Body"]
            try:
                return body.read(n)
            finally:
                body.close()
        except Exception as exc:
            code, status = _status(exc)
            if code == "InvalidRange" or status == 416:
                return b""  # S3 refuses any range of an empty object
            raise _read_error("get-head", key, exc) from exc

    def size(self, key: str) -> int | None:
        try:
            resp = self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            if _is_missing(exc):
                return None
            raise _read_error("head", key, exc) from exc
        return int(resp["ContentLength"])

    def get(self, key: str) -> bytes:
        data = self.get_raw(key)
        if _is_sealed(data):
            raise SealedObjectError(f"{key!r} is sealed; read it through OriginalsStore")
        return data

    def iter_objects(self, prefix: str) -> Iterator[tuple[str, datetime]]:
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    yield obj["Key"], obj["LastModified"]
        except Exception as exc:
            raise _read_error("list", prefix, exc) from exc

    def exists(self, key: str) -> bool:
        return self.size(key) is not None

    def delete(self, key: str) -> bool:
        if not self.exists(key):
            return False
        self._client.delete_object(Bucket=self._bucket, Key=key)
        return True
