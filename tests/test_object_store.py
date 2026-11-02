"""Object-storage seam: in-memory double, S3 driver config, pipeline fetch-by-key,
and an opt-in integration round-trip against a live SeaweedFS (skipped if absent)."""
import os

import pytest

from wordsworth.object_store import (
    InMemoryObjectStore,
    ObjectStore,
    ObjectStoreError,
    S3ObjectStore,
    SealedObjectError,
)
from wordsworth.document_keys import DocumentKeys
from wordsworth.originals_envelope import seal
from wordsworth.originals_store import OriginalsStore
from wordsworth.pipeline import ingest, process
from wordsworth.states import State
from wordsworth.transit import FakeTransit

SEALED = seal(b"k" * 32, "a" * 12, "documents/sealed", b"%PDF-1.4 secret")


# --- In-memory double (task 1.3) -------------------------------------------

def test_put_get_round_trip():
    store = InMemoryObjectStore()
    store.put("documents/a", b"hello bytes")
    assert store.get("documents/a") == b"hello bytes"


def test_exists_reflects_presence():
    store = InMemoryObjectStore()
    assert store.exists("nope") is False
    store.put("here", b"x")
    assert store.exists("here") is True


def test_in_memory_double_satisfies_protocol():
    assert isinstance(InMemoryObjectStore(), ObjectStore)


def test_missing_key_errors_clearly():
    store = InMemoryObjectStore()
    with pytest.raises(ObjectStoreError, match="get 'ghost' failed"):
        store.get("ghost")


# --- the sealed-object guard (task 3.3) -------------------------------------

def test_in_memory_get_refuses_a_sealed_object():
    store = InMemoryObjectStore()
    store.put("documents/sealed", SEALED)
    with pytest.raises(SealedObjectError):
        store.get("documents/sealed")


def test_in_memory_get_still_returns_a_header_less_object():
    store = InMemoryObjectStore()
    store.put("documents/plain", b"%PDF-1.4 plain bytes")
    assert store.get("documents/plain") == b"%PDF-1.4 plain bytes"


def test_in_memory_get_raw_returns_sealed_bytes_unchanged():
    store = InMemoryObjectStore()
    store.put("documents/sealed", SEALED)
    assert store.get_raw("documents/sealed") == SEALED


def test_in_memory_iter_objects_yields_key_and_last_modified():
    store = InMemoryObjectStore()
    store.put("documents/a", b"x")
    store.put("other/b", b"y")
    found = dict(store.iter_objects("documents/"))
    assert list(found) == ["documents/a"]
    assert found["documents/a"].tzinfo is not None


# --- Sovereign credentials (invariant): read from secret source, not code ---

def test_s3_from_config_requires_credentials(monkeypatch):
    for var in ("WORDSWORTH_S3_ACCESS_KEY", "WORDSWORTH_S3_SECRET_KEY"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ObjectStoreError, match="SOPS\\+age or OpenBao"):
        S3ObjectStore.from_config()


def test_s3_from_config_reads_credentials_from_env(monkeypatch):
    # Creds arrive via the env (injected by SOPS+age/OpenBao), never hardcoded.
    monkeypatch.setenv("WORDSWORTH_S3_ACCESS_KEY", "AKIA_FROM_SECRET_SOURCE")
    monkeypatch.setenv("WORDSWORTH_S3_SECRET_KEY", "SECRET_FROM_SECRET_SOURCE")
    monkeypatch.setenv("WORDSWORTH_S3_ENDPOINT_URL", "http://localhost:8333")
    monkeypatch.setenv("WORDSWORTH_S3_BUCKET", "wordsworth-test")
    boto3 = pytest.importorskip("boto3")

    captured = {}

    def fake_client(service, **kwargs):
        captured.update(service=service, **kwargs)
        return object()

    monkeypatch.setattr(boto3, "client", fake_client)
    store = S3ObjectStore.from_config()
    assert captured["service"] == "s3"
    assert captured["aws_access_key_id"] == "AKIA_FROM_SECRET_SOURCE"
    assert captured["aws_secret_access_key"] == "SECRET_FROM_SECRET_SOURCE"
    assert captured["endpoint_url"] == "http://localhost:8333"
    assert store._bucket == "wordsworth-test"


# --- Pipeline fetch-by-key (task 2.2) --------------------------------------

def test_pipeline_reads_bytes_from_store(session, born_digital_pdf, mem_index,
                                         fake_embedder, mem_originals):
    doc = ingest(session, mem_originals, born_digital_pdf)
    session.commit()
    # process receives no bytes; it must fetch them from the store by object_key.
    final = process(session, doc.id, mem_originals, search_index=mem_index,
                    embedder=fake_embedder)
    session.commit()
    assert final == State.INDEXED


def test_pipeline_missing_object_errors_clearly(session, born_digital_pdf,
                                                mem_index, fake_embedder, mem_originals):
    doc = ingest(session, mem_originals, born_digital_pdf)
    session.commit()
    # the recorded key is absent here
    empty = OriginalsStore(InMemoryObjectStore(), DocumentKeys(lambda n: FakeTransit()))
    with pytest.raises(ObjectStoreError, match="failed"):
        process(session, doc.id, empty, search_index=mem_index,
                embedder=fake_embedder)


# --- S3 driver: get_raw, iter_objects, the sealed guard (task 3.3) ---------

class _FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeS3Client:
    """Just enough of boto3's S3 client for get/get_raw/iter_objects."""

    def __init__(self):
        self._objects: dict[str, bytes] = {}

    def put_object(self, Bucket, Key, Body):
        self._objects[Key] = Body

    def get_object(self, Bucket, Key):
        return {"Body": _FakeBody(self._objects[Key])}

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        return self

    def paginate(self, Bucket, Prefix):
        import datetime as dt

        contents = [{"Key": k, "LastModified": dt.datetime.now(dt.timezone.utc)}
                    for k in self._objects if k.startswith(Prefix)]
        yield {"Contents": contents}


def test_s3_get_refuses_a_sealed_object():
    store = S3ObjectStore(_FakeS3Client(), "bucket")
    store.put("documents/sealed", SEALED)
    with pytest.raises(SealedObjectError):
        store.get("documents/sealed")


def test_s3_get_still_returns_a_header_less_object():
    store = S3ObjectStore(_FakeS3Client(), "bucket")
    store.put("documents/plain", b"%PDF-1.4 plain bytes")
    assert store.get("documents/plain") == b"%PDF-1.4 plain bytes"


def test_s3_get_raw_returns_sealed_bytes_unchanged():
    store = S3ObjectStore(_FakeS3Client(), "bucket")
    store.put("documents/sealed", SEALED)
    assert store.get_raw("documents/sealed") == SEALED


def test_s3_iter_objects_yields_key_and_last_modified():
    store = S3ObjectStore(_FakeS3Client(), "bucket")
    store.put("documents/a", b"x")
    store.put("other/b", b"y")
    found = dict(store.iter_objects("documents/"))
    assert list(found) == ["documents/a"]


# --- Integration against a live SeaweedFS (task 3.1) -----------------------

def test_s3_round_trip_against_seaweedfs(monkeypatch):
    pytest.importorskip("boto3")
    endpoint = os.environ.get("WORDSWORTH_S3_ENDPOINT_URL", "http://localhost:8333")
    monkeypatch.setenv("WORDSWORTH_S3_ENDPOINT_URL", endpoint)
    monkeypatch.setenv("WORDSWORTH_S3_ACCESS_KEY",
                       os.environ.get("WORDSWORTH_S3_ACCESS_KEY", "any"))
    monkeypatch.setenv("WORDSWORTH_S3_SECRET_KEY",
                       os.environ.get("WORDSWORTH_S3_SECRET_KEY", "any"))
    bucket = "wordsworth-it"
    monkeypatch.setenv("WORDSWORTH_S3_BUCKET", bucket)
    store = S3ObjectStore.from_config()
    try:
        store._client.create_bucket(Bucket=bucket)
    except Exception as exc:  # bucket exists is fine; unreachable -> skip
        if "BucketAlreadyOwnedByYou" not in str(exc) and "exists" not in str(exc):
            pytest.skip(f"SeaweedFS not reachable: {exc}")
    store.put("documents/it", b"seaweed bytes")
    assert store.exists("documents/it") is True
    assert store.get("documents/it") == b"seaweed bytes"
