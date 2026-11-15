# SPDX-License-Identifier: MIT
"""Shared setup for the `wordsworth-seal-originals` race and repair tests
(review of #484): a store that runs a deletion in another session at a chosen
moment, stores that corrupt the final key, a key service that is down, and
the checks for "the deleted document stayed deleted"."""
from __future__ import annotations

import time

from race_setup import run as run_thread
from sqlalchemy import text

from wordsworth.audit import current_state
from wordsworth.deletion import delete_document
from wordsworth.document_keys import DocumentKeys
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.originals_seal import TEMP_PREFIX
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State
from wordsworth.transit import FakeTransit

from shred_setup import key_row

MARKER = b"TOTALLY-SECRET-PLAINTEXT-MARKER"
PLAINTEXT = b"%PDF-1.4 " + MARKER + b" rest of the document"


def fake_keys() -> DocumentKeys:
    return DocumentKeys(lambda name: FakeTransit())


def temp_key(object_key: str) -> str:
    return TEMP_PREFIX + object_key.rsplit("/", 1)[-1]


def delete_now(session_factory, store, document_id) -> None:
    with session_factory() as s:
        delete_document(s, document_id, store, InMemoryIndex(), actor="t")
        s.commit()


def _lock_waiters(session_factory) -> int:
    with session_factory() as probe:
        return probe.execute(text(
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE datname = current_database() AND wait_event_type = 'Lock' "
            "AND pid <> pg_backend_pid()")).scalar_one()


class DeletingStore(InMemoryObjectStore):
    """Runs a deletion of ``document_id`` in another session (a thread) the
    first time ``op`` (``"get_raw"`` or ``"put"``) touches ``key``, right
    after the operation itself, and goes on once that deletion has either
    committed or is waiting on a lock -- whichever the code under test lets
    happen (``waited``: it was still waiting). ``join()`` waits for it and
    re-raises its error."""

    def __init__(self, session_factory):
        super().__init__()
        self._session_factory = session_factory
        self._trigger = None
        self._thread = None
        self._errors: dict = {}
        self.waited = False

    def arm(self, op: str, key: str, document_id) -> None:
        self._trigger = (op, key, document_id)

    def _maybe_delete(self, op: str, key: str) -> None:
        if self._trigger is None or self._trigger[:2] != (op, key):
            return
        document_id, self._trigger = self._trigger[2], None
        self._thread = run_thread(self._errors, "delete", lambda: delete_now(
            self._session_factory, self, document_id))
        deadline = time.monotonic() + 15
        while self._thread.is_alive() and not _lock_waiters(self._session_factory):
            assert time.monotonic() < deadline, "the deletion neither ran nor waited"
            time.sleep(0.05)
        self.waited = self._thread.is_alive()  # blocked by the seal's row lock

    def get_raw(self, key):
        data = super().get_raw(key)
        self._maybe_delete("get_raw", key)
        return data

    def put(self, key, data):
        super().put(key, data)
        self._maybe_delete("put", key)

    def join(self) -> None:
        assert self._thread is not None, "the deletion never started"
        self._thread.join(30)
        assert not self._thread.is_alive(), "the deletion never finished"
        assert not self._errors, self._errors


def assert_stayed_deleted(session_factory, store, document_id, object_key) -> None:
    """Deleted, no key row, nothing at the final key or the temporary key."""
    with session_factory() as s:
        assert current_state(s, document_id) == State.DELETED
        assert key_row(s, object_key) is None
    assert not store.exists(object_key)
    assert not store.exists(temp_key(object_key))


def _flip_last_byte(data: bytes) -> bytes:
    out = bytearray(data)
    out[-1] ^= 0x01
    return bytes(out)


class CorruptFinalWriteStore(InMemoryObjectStore):
    """Corrupts the first sealed write to a `documents/` key (a bad overwrite)."""

    def __init__(self):
        super().__init__()
        self.corrupted = 0

    def put(self, key, data):
        if key.startswith("documents/") and data.startswith(b"WWENC") and not self.corrupted:
            self.corrupted += 1
            data = _flip_last_byte(data)
        super().put(key, data)


class CorruptFinalReadStore(InMemoryObjectStore):
    """Corrupts every read of a sealed object at ``key`` (the final key)."""

    def __init__(self, key: str):
        super().__init__()
        self._key = key

    def get_raw(self, key):
        data = super().get_raw(key)
        if key == self._key and data.startswith(b"WWENC"):
            return _flip_last_byte(data)
        return data


class DownTransit:
    def wrap(self, plaintext: bytes) -> bytes:
        raise ConnectionError("key service unreachable: " + MARKER.decode())

    def unwrap(self, ciphertext: bytes) -> bytes:
        raise ConnectionError("key service unreachable: " + MARKER.decode())
