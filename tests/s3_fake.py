# SPDX-License-Identifier: MIT
"""A boto3-shaped S3 client for the object-store read tests: answers like S3
(ranged GETs, HEAD with ContentLength, 404 as a ClientError, 416 for a range
of an empty object), and can break the way production did on 2026-11-15 -- a
full GET whose body stops mid-stream with urllib3's IncompleteRead."""
from __future__ import annotations

import datetime as dt

from botocore.exceptions import ClientError
from urllib3.exceptions import IncompleteRead, ProtocolError


def client_error(code: str, status: int, op: str = "GetObject") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code},
                        "ResponseMetadata": {"HTTPStatusCode": status}}, op)


def incomplete_read() -> ProtocolError:
    return ProtocolError("Connection broken: IncompleteRead(4096 bytes read, "
                         "13000000 more expected)", IncompleteRead(4096, 13000000))


class FakeBody:
    def __init__(self, data: bytes, broken: bool = False):
        self._data = data
        self._broken = broken
        self.closed = False

    def read(self, amt: int | None = None) -> bytes:
        if self._broken:
            raise incomplete_read()
        return self._data if amt is None else self._data[:amt]

    def close(self) -> None:
        self.closed = True


class FakeS3Client:
    """``break_full_reads``: a GET without a Range header breaks mid-body.
    ``down``: every call raises ``down`` (an exception instance)."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.break_full_reads = False
        self.down: Exception | None = None
        self.calls: list[tuple[str, str, str | None]] = []

    def _check(self, op: str, key: str, rng: str | None = None) -> None:
        self.calls.append((op, key, rng))
        if self.down is not None:
            raise self.down
        if op in ("get", "head") and key not in self.objects:
            raise client_error("NoSuchKey" if op == "get" else "404", 404)

    def put_object(self, Bucket, Key, Body):
        self._check("put", Key)
        self.objects[Key] = bytes(Body)

    def get_object(self, Bucket, Key, Range=None):
        self._check("get", Key, Range)
        data = self.objects[Key]
        if Range is None:
            return {"Body": FakeBody(data, broken=self.break_full_reads)}
        if not data:
            raise client_error("InvalidRange", 416)
        start, end = Range.removeprefix("bytes=").split("-")
        return {"Body": FakeBody(data[int(start):int(end) + 1])}

    def head_object(self, Bucket, Key):
        self._check("head", Key)
        return {"ContentLength": len(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self._check("delete", Key)
        self.objects.pop(Key, None)

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return self

    def paginate(self, Bucket, Prefix):
        self._check("list", Prefix)
        now = dt.datetime.now(dt.timezone.utc)
        yield {"Contents": [{"Key": k, "LastModified": now}
                            for k in self.objects if k.startswith(Prefix)]}

    def full_gets(self) -> list[str]:
        return [key for op, key, rng in self.calls if op == "get" and rng is None]
