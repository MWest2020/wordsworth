# SPDX-License-Identifier: MIT
"""Shared setup for the ingest-versus-deletion race tests (#452): an originals
store that records which document every `put_original` was for, a thread
runner that keeps the exception, and a probe for a session waiting on a lock."""
from __future__ import annotations

import threading
import time

from sqlalchemy import select, text

from wordsworth.document_keys import DocumentKeyRecord, DocumentKeys
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.originals_store import OriginalsStore
from wordsworth.transit import FakeTransit

PDF = b"%PDF-1.4 an original that must stay deleted"


class SpyOriginalsStore(OriginalsStore):
    """Records the document id of every `put_original` call and runs
    ``on_put`` (if set) first; runs ``on_delete(key)`` (if set) after a
    delete."""

    def __init__(self):
        super().__init__(InMemoryObjectStore(), DocumentKeys(lambda name: FakeTransit()))
        self.put_for: list = []
        self.on_put = None
        self.on_delete = None

    def put_original(self, session, document_id, object_key, data):
        if self.on_put is not None:
            self.on_put()
        self.put_for.append(document_id)
        return super().put_original(session, document_id, object_key, data)

    def delete(self, key):
        gone = super().delete(key)
        if self.on_delete is not None:
            self.on_delete(key)
        return gone


def key_rows_for(session, document_id) -> set[str]:
    """The key ids of the key rows carrying ``document_id``, as committed now."""
    return set(session.execute(
        select(DocumentKeyRecord.key_id)
        .where(DocumentKeyRecord.document_id == document_id)
    ).scalars().all())


def run(errors: dict, name: str, fn) -> threading.Thread:
    def target():
        try:
            fn()
        except Exception as exc:  # surfaced by the assertion on `errors`
            errors[name] = exc
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread


def wait_for_a_lock_waiter(session_factory, timeout: float = 10.0) -> None:
    """Return once some other session of this database waits on a lock."""
    deadline = time.monotonic() + timeout
    with session_factory() as probe:
        while time.monotonic() < deadline:
            waiting = probe.execute(text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND wait_event_type = 'Lock' "
                "AND pid <> pg_backend_pid()")).scalar_one()
            if waiting:
                return
            probe.rollback()
            time.sleep(0.05)
    raise AssertionError("no session started waiting on a lock")


def pause_process(monkeypatch, where: str, paused: threading.Event,
                  resume: threading.Event) -> None:
    """Hold `pipeline.process` until ``resume`` is set (#462): ``"anonymized"``
    right after its ANONYMIZED record (so it holds the chain lock),
    ``"profile"`` before its first audit append."""
    from wordsworth import pipeline
    from wordsworth.states import State

    def hold():
        paused.set()
        assert resume.wait(30), "never resumed"

    if where == "profile":
        real_profile = pipeline.profile_pdf

        def profile(*args, **kwargs):
            hold()
            return real_profile(*args, **kwargs)
        monkeypatch.setattr(pipeline, "profile_pdf", profile)
        return
    real = pipeline.transition

    def transition(session, document_id, to_state, **kwargs):
        record = real(session, document_id, to_state, **kwargs)
        if to_state == State.ANONYMIZED:
            hold()
        return record
    monkeypatch.setattr(pipeline, "transition", transition)
