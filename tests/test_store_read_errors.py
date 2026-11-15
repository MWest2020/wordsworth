# SPDX-License-Identifier: MIT
"""Only `ObjectMissingError` means "not there" (review of #488). Since the S3
driver wraps every read error -- a body broken off mid-stream included -- in
ObjectStoreError, a caller that read any ObjectStoreError as absent would
act on an object it merely failed to read: `put_original` would mint a key
and overwrite a legacy plaintext (rules 2/3) instead of leaving it (rule 4),
and the orphan sweep would skip an object silently."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from s3_fake import FakeS3Client
from sqlalchemy import select

from wordsworth.document_keys import DocumentKeyRecord, DocumentKeys
from wordsworth.object_store import InMemoryObjectStore, ObjectStoreError, S3ObjectStore
from wordsworth.originals_envelope import seal
from wordsworth.originals_store import OriginalsStore
from wordsworth.pipeline import register
from wordsworth.sealed_orphans import find_orphans
from wordsworth.transit import FakeTransit

KEY = "documents/" + "a" * 64
LEGACY = b"%PDF-1.4 the only readable copy of this document"
LATER = datetime.now(timezone.utc) + timedelta(hours=2)


def _keys() -> DocumentKeys:
    return DocumentKeys(lambda name: FakeTransit())


@pytest.mark.parametrize("pending_row", [False, True])
def test_ingest_refuses_rather_than_overwrites_an_unreadable_legacy_object(
        session, pending_row):
    """A full read that breaks mid-body is not "missing": put_original raises,
    and the legacy plaintext, the only copy, stays exactly as it was."""
    keys = _keys()
    doc = register(session, KEY)
    session.flush()
    if pending_row:
        keys.mint(session, doc.id, KEY, "_global")
        session.flush()
    rows_before = session.execute(select(DocumentKeyRecord)).scalars().all()
    client = FakeS3Client()
    client.objects[KEY] = LEGACY
    client.break_full_reads = True

    store = OriginalsStore(S3ObjectStore(client, "bucket"), keys)
    with pytest.raises(ObjectStoreError):
        store.put_original(session, doc.id, KEY, LEGACY)
    assert client.objects[KEY] == LEGACY
    assert not [c for c in client.calls if c[0] == "put"]
    assert session.execute(select(DocumentKeyRecord)).scalars().all() == rows_before


class _CountingStore(InMemoryObjectStore):
    full_reads = 0

    def get_raw(self, key):
        self.full_reads += 1
        return super().get_raw(key)


def test_orphan_sweep_reads_only_the_header(session):
    objects = _CountingStore()
    sealed = seal(os.urandom(32), "a" * 12, "documents/orphan", b"x" * 100_000)
    objects.put("documents/orphan", sealed)
    objects.put("documents/legacy", LEGACY)

    found = find_orphans(session, objects, now=LATER)
    assert [key for key, _ in found] == ["documents/orphan"]
    assert objects.full_reads == 0


def test_orphan_sweep_does_not_skip_an_unreadable_object(session):
    client = FakeS3Client()
    store = S3ObjectStore(client, "bucket")
    store.put("documents/orphan", seal(os.urandom(32), "a" * 12, "documents/orphan", b"x"))
    real_get = client.get_object

    def broken_get(**kwargs):
        raise ConnectionResetError("reset by peer")
    client.get_object = broken_get
    old = datetime.now(timezone.utc) - timedelta(hours=3)
    client.paginate = lambda Bucket, Prefix: iter(
        [{"Contents": [{"Key": "documents/orphan", "LastModified": old}]}])
    with pytest.raises(ObjectStoreError):
        find_orphans(session, store)
    client.get_object = real_get
    assert [key for key, _ in find_orphans(session, store)] == ["documents/orphan"]


@pytest.mark.parametrize("module", ["wordsworth.object_store_s3",
                                    "wordsworth.object_store"])
def test_each_store_module_imports_first_in_a_fresh_interpreter(module):
    done = subprocess.run([sys.executable, "-c", f"import {module}"],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr


def test_an_empty_object_is_legacy_without_a_header_read():
    from wordsworth.seal_candidates import probe

    client = FakeS3Client()
    client.objects["documents/empty"] = b""
    assert probe(S3ObjectStore(client, "bucket"), "documents/empty") == ("legacy", 0, b"")
    assert [op for op, _key, _rng in client.calls] == ["head"]
