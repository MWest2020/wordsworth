# SPDX-License-Identifier: MIT
"""The object store's cheap reads (`get_head`, `size`) and its error boundary:
every S3 read error leaves the driver as an ObjectStoreError -- an
`ObjectMissingError` only when the store said the key does not exist. Plus an
opt-in round-trip of the ranged read against a live SeaweedFS (skipped if
absent), since that is the backend production runs on."""
from __future__ import annotations

import os

import pytest
from botocore.exceptions import ReadTimeoutError
from s3_fake import FakeS3Client, client_error, incomplete_read

from wordsworth.object_store import (
    InMemoryObjectStore,
    ObjectMissingError,
    ObjectStore,
    ObjectStoreError,
    S3ObjectStore,
)
from wordsworth.originals_store import OriginalsStore

DATA = b"WWENC\x01" + b"k" * 12 + b"n" * 12 + b"ciphertext" * 100


@pytest.fixture
def s3():
    client = FakeS3Client()
    return S3ObjectStore(client, "bucket"), client


def test_in_memory_head_and_size():
    store = InMemoryObjectStore()
    store.put("documents/a", DATA)
    assert store.get_head("documents/a", 5) == b"WWENC"
    assert store.size("documents/a") == len(DATA)
    assert store.size("documents/ghost") is None
    with pytest.raises(ObjectMissingError):
        store.get_head("documents/ghost", 5)


def test_every_store_still_satisfies_the_protocol():
    assert isinstance(InMemoryObjectStore(), ObjectStore)
    assert isinstance(S3ObjectStore(FakeS3Client(), "b"), ObjectStore)
    assert isinstance(OriginalsStore(InMemoryObjectStore(), keys=None), ObjectStore)


def test_s3_get_head_is_a_ranged_read(s3):
    store, client = s3
    client.objects["documents/a"] = DATA
    assert store.get_head("documents/a", 30) == DATA[:30]
    assert client.calls[-1] == ("get", "documents/a", "bytes=0-29")
    assert client.full_gets() == []


def test_s3_get_head_of_an_empty_object_is_empty(s3):
    store, client = s3
    client.objects["documents/empty"] = b""
    assert store.get_head("documents/empty", 30) == b""


def test_s3_size_is_a_head_and_none_when_missing(s3):
    store, client = s3
    client.objects["documents/a"] = DATA
    assert store.size("documents/a") == len(DATA)
    assert store.size("documents/ghost") is None
    assert store.exists("documents/a") is True
    assert store.exists("documents/ghost") is False
    assert client.full_gets() == []


def test_s3_missing_key_is_object_missing(s3):
    store, _client = s3
    with pytest.raises(ObjectMissingError, match="get 'documents/ghost' failed"):
        store.get_raw("documents/ghost")
    with pytest.raises(ObjectMissingError):
        store.get_head("documents/ghost", 30)


def test_s3_broken_body_is_an_object_store_error_not_missing(s3):
    """Production, 2026-11-15: a 13 MB GET broke off with IncompleteRead and,
    not being an ObjectStoreError, ended the whole run."""
    store, client = s3
    client.objects["documents/big"] = DATA
    client.break_full_reads = True
    with pytest.raises(ObjectStoreError) as caught:
        store.get_raw("documents/big")
    assert not isinstance(caught.value, ObjectMissingError)
    assert store.get_head("documents/big", 5) == b"WWENC"  # the ranged read still works


@pytest.mark.parametrize("error", [
    client_error("InternalError", 500),
    client_error("SlowDown", 503),
    incomplete_read(),
    ReadTimeoutError(endpoint_url="http://seaweedfs:8333"),
    ConnectionResetError("reset by peer"),
])
def test_s3_every_read_error_is_wrapped(s3, error):
    store, client = s3
    client.objects["documents/a"] = DATA
    client.down = error
    for read in (lambda: store.get_raw("documents/a"),
                 lambda: store.get_head("documents/a", 30),
                 lambda: store.size("documents/a"),
                 lambda: store.exists("documents/a"),
                 lambda: list(store.iter_objects("documents/"))):
        with pytest.raises(ObjectStoreError) as caught:
            read()
        assert not isinstance(caught.value, ObjectMissingError)


def test_s3_get_head_against_seaweedfs(monkeypatch):
    pytest.importorskip("boto3")
    for var, default in (("WORDSWORTH_S3_ENDPOINT_URL", "http://localhost:8333"),
                         ("WORDSWORTH_S3_ACCESS_KEY", "any"),
                         ("WORDSWORTH_S3_SECRET_KEY", "any")):
        monkeypatch.setenv(var, os.environ.get(var, default))
    monkeypatch.setenv("WORDSWORTH_S3_BUCKET", "wordsworth-it")
    store = S3ObjectStore.from_config()
    try:
        store._client.create_bucket(Bucket="wordsworth-it")
    except Exception as exc:  # bucket exists is fine; unreachable -> skip
        if "BucketAlreadyOwnedByYou" not in str(exc) and "exists" not in str(exc):
            pytest.skip(f"SeaweedFS not reachable: {exc}")
    store.put("documents/it-head", DATA)
    store.put("documents/it-empty", b"")
    assert store.get_head("documents/it-head", 30) == DATA[:30]
    assert store.size("documents/it-head") == len(DATA)
    assert store.get_head("documents/it-empty", 30) == b""
    assert store.size("documents/it-ghost") is None
    with pytest.raises(ObjectMissingError):
        store.get_head("documents/it-ghost", 30)
