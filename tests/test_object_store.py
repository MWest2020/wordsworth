"""Object-storage seam: in-memory double, S3 driver config, pipeline fetch-by-key,
and an opt-in integration round-trip against a live SeaweedFS (skipped if absent)."""
import os

import pytest

from wordsworth.object_store import (
    InMemoryObjectStore,
    ObjectStore,
    ObjectStoreError,
    S3ObjectStore,
)
from wordsworth.pipeline import ingest, process
from wordsworth.states import State


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
                                         fake_embedder, mem_store):
    doc = ingest(session, mem_store, born_digital_pdf)
    session.commit()
    # process receives no bytes; it must fetch them from the store by object_key.
    final = process(session, doc.id, mem_store, search_index=mem_index,
                    embedder=fake_embedder)
    session.commit()
    assert final == State.INDEXED


def test_pipeline_missing_object_errors_clearly(session, born_digital_pdf,
                                                mem_index, fake_embedder, mem_store):
    doc = ingest(session, mem_store, born_digital_pdf)
    session.commit()
    empty = InMemoryObjectStore()  # the recorded key is absent here
    with pytest.raises(ObjectStoreError, match="failed"):
        process(session, doc.id, empty, search_index=mem_index,
                embedder=fake_embedder)


# --- Integration against a live SeaweedFS (task 3.1) -----------------------

def test_s3_round_trip_against_seaweedfs(monkeypatch):
    boto3 = pytest.importorskip("boto3")
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
