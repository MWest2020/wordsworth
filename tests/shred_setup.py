# SPDX-License-Identifier: MIT
"""Shared setup for the `originals-crypto-shred` tests: a `FakeTransit` that
counts its unwraps (FakeTransit itself does not count), an originals store
over it, a sealed document, and "restore a backup of the object store and try
to open it"."""
from __future__ import annotations

from sqlalchemy import select

from wordsworth.document_keys import DocumentKeyRecord, DocumentKeys
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.originals_io import write_original
from wordsworth.originals_store import OriginalsStore
from wordsworth.pipeline import register
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
