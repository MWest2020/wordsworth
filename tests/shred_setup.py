# SPDX-License-Identifier: MIT
"""Shared setup for the `originals-crypto-shred` tests: a `FakeTransit` that
counts its unwraps (FakeTransit itself does not count), an originals store
over it, a sealed document, "restore a backup of the object store and try to
open it", a copy and its survivor, and a probe for a session waiting on a
lock."""
from __future__ import annotations

import time

from sqlalchemy import select, text

from wordsworth.document_keys import DocumentKeyRecord, DocumentKeys
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.originals_io import write_original
from wordsworth.originals_store import OriginalsStore
from wordsworth.pipeline import register
from wordsworth.supersession import supersede
from wordsworth.transit import FakeTransit

PDF = b"%PDF-1.4 a sealed original nobody may read after the delete"
KEY = "documents/" + "5d" * 32


class CountingTransit:
    """Wraps one `FakeTransit` (one KEK for every name) and counts `unwrap`
    calls, so a test can tell a cache hit from a call to the key service."""

    def __init__(self):
        self._inner = FakeTransit()
        self.unwraps = 0

    def wrap(self, plaintext: bytes) -> bytes:
        return self._inner.wrap(plaintext)

    def unwrap(self, ciphertext: bytes) -> bytes:
        self.unwraps += 1
        return self._inner.unwrap(ciphertext)

    def transit_for(self, name: str) -> "CountingTransit":
        return self


def keys_over(transit: CountingTransit, **kw) -> DocumentKeys:
    return DocumentKeys(transit.transit_for, **kw)


def originals(transit: CountingTransit | None = None,
              objects: InMemoryObjectStore | None = None) -> OriginalsStore:
    transit = transit or CountingTransit()
    return OriginalsStore(objects or InMemoryObjectStore(), keys_over(transit))


def sealed(session, store: OriginalsStore, key: str = KEY, data: bytes = PDF,
           *, document_id=None):
    """Register a document on ``key`` (unless ``document_id`` names one that
    already exists) and write ``data`` sealed under it; returns the id."""
    if document_id is None:
        document_id = register(session, key).id
        session.flush()
    write_original(session, store, document_id, key, data)
    session.flush()
    return document_id


def key_row(session, object_key: str = KEY) -> DocumentKeyRecord | None:
    """The key row as committed now -- a select, never the identity map."""
    return session.execute(
        select(DocumentKeyRecord).where(DocumentKeyRecord.object_key == object_key)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def opens_from_backup(session, backup: dict[str, bytes], object_key: str = KEY,
                      transit: CountingTransit | None = None) -> bytes:
    """Restore ``backup`` (object key -> raw sealed bytes, taken before the
    deletion) into a fresh object store and read it through a fresh key
    store with a cold cache, as a restore of the object store would."""
    objects = InMemoryObjectStore()
    for key, raw in backup.items():
        objects.put(key, raw)
    return originals(transit, objects).get_original(session, object_key)


def pair(session_factory, *, row_carries: str = "survivor", plaintext: bool = False):
    """A survivor and a superseded copy on one object key, sealed once; the
    key row carries the id ``row_carries`` names (both happen: `put_original`
    re-points a row on a re-ingest and leaves it on a reseal). ``plaintext``:
    a legacy plaintext object and no key row instead."""
    transit = CountingTransit()
    store = originals(transit)
    with session_factory() as s:
        survivor, copy = register(s, KEY), register(s, KEY)
        s.flush()
        if plaintext:
            store.objects.put(KEY, b"%PDF-1.4 legacy plaintext, never sealed")
        else:
            sealed(s, store, document_id=survivor.id)
        if row_carries == "copy":
            key_row(s).document_id = copy.id
        supersede(s, copy.id, survivor.id, actor="t")
        s.commit()
        return store, transit, survivor.id, copy.id


def wait_for_a_lock_waiter(session_factory, timeout=10.0):
    with session_factory() as probe:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            waiting = probe.execute(text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND wait_event_type = 'Lock'"
            )).scalar_one()
            if waiting:
                return
            probe.rollback()
            time.sleep(0.05)
    raise AssertionError("the second deletion never waited for a lock")
