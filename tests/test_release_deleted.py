# SPDX-License-Identifier: MIT
"""`wordsworth-release-deleted-keys` (task 2.1): the one-off release for
documents deleted before `deleted-document-releases-object-key` -- lists
without `--apply`, releases with it, one `release-key` audit record per
document, a second run finds nothing, and a live document is never touched."""
from __future__ import annotations

from sqlalchemy import select

from wordsworth.audit import verify_chain
from wordsworth.models import AuditRecord, Document
from wordsworth.pipeline import register, transition
from wordsworth.release_deleted import find_candidates, run
from wordsworth.states import State


def _session_factory(session):
    """A fake session_factory for `run`, which opens-and-closes a session."""
    class _Ctx:
        def __enter__(self):
            return session

        def __exit__(self, *exc):
            return False

    return lambda: _Ctx()


def _pre_change_deleted(session, key):
    """A document deleted before this change: `deleted`, its real (content)
    key untouched -- exactly the shape `deletion.py` no longer leaves behind,
    and what this command exists to find."""
    doc = register(session, key)
    session.flush()
    transition(session, doc.id, State.DELETED, step="delete", payload={"actor": "t"})
    session.commit()
    return doc


def test_dry_run_lists_without_releasing(session):
    key = "documents/" + "aa" * 32
    doc = _pre_change_deleted(session, key)

    assert find_candidates(session) == [(doc.id, key)]

    report = run(_session_factory(session), apply=False)
    assert report["found"] == [str(doc.id)]
    assert report["applied"] is False
    assert session.get(Document, doc.id).object_key == key
    assert session.execute(
        select(AuditRecord).where(AuditRecord.document_id == doc.id,
                                  AuditRecord.step == "release-key")).first() is None


def test_apply_releases_and_writes_one_release_key_record(session):
    key = "documents/" + "bb" * 32
    doc = _pre_change_deleted(session, key)

    report = run(_session_factory(session), apply=True)
    assert report["found"] == [str(doc.id)]
    assert report["released"] == [str(doc.id)]

    assert session.get(Document, doc.id).object_key == f"deleted/{doc.id}"
    rec = session.execute(
        select(AuditRecord).where(AuditRecord.document_id == doc.id,
                                  AuditRecord.step == "release-key")).scalar_one()
    assert rec.from_state == "deleted" and rec.to_state == "deleted"
    assert rec.payload == {"released_object_key": key}
    # no value, text, token or filename -- only the former key, itself an id
    assert key not in str({k: v for k, v in rec.payload.items() if k != "released_object_key"})

    ok, bad = verify_chain(session)
    assert ok and bad is None


def test_a_second_run_finds_nothing(session):
    key = "documents/" + "cc" * 32
    doc = _pre_change_deleted(session, key)
    run(_session_factory(session), apply=True)

    assert find_candidates(session) == []
    report = run(_session_factory(session), apply=True)
    assert report["found"] == []
    assert report["released"] == []
    count = session.execute(
        select(AuditRecord).where(AuditRecord.document_id == doc.id,
                                  AuditRecord.step == "release-key")).all()
    assert len(count) == 1  # not released a second time


def test_a_live_document_is_never_touched(session):
    key = "documents/" + "dd" * 32
    doc = register(session, key)
    session.commit()

    assert find_candidates(session) == []
    report = run(_session_factory(session), apply=True)
    assert report["found"] == []
    assert session.get(Document, doc.id).object_key == key
