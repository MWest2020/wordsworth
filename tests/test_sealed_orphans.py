# SPDX-License-Identifier: MIT
"""`wordsworth-sealed-orphans` (task 4.1): lists and, with `--apply`, removes
sealed objects under `documents/` that open under no key row and are older
than one hour."""
import os
from datetime import datetime, timedelta, timezone

from wordsworth.document_keys import DocumentKeys
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.originals_envelope import seal
from wordsworth.pipeline import register
from wordsworth.sealed_orphans import find_orphans, run
from wordsworth.transit import FakeTransit

LATER = datetime.now(timezone.utc) + timedelta(hours=2)


def _transit_for(name):
    return FakeTransit()


def _session_factory(session):
    """A fake session_factory for `run`, which opens-and-closes a session."""
    class _Ctx:
        def __enter__(self):
            return session

        def __exit__(self, *exc):
            return False

    return lambda: _Ctx()


def test_orphan_without_a_row_is_listed_and_removed_on_apply(session):
    objects = InMemoryObjectStore()
    objects.put("documents/orphan", seal(os.urandom(32), "a" * 12, "documents/orphan", b"x"))

    found = find_orphans(session, objects, now=LATER)
    assert found == [("documents/orphan", objects._modified["documents/orphan"])]

    report = run(_session_factory(session), objects, apply=True, now=LATER)
    assert report["found"] == ["documents/orphan"]
    assert report["removed"] == ["documents/orphan"]
    assert not objects.exists("documents/orphan")


def test_orphan_with_a_mismatched_row_is_listed_and_removed_on_apply(session):
    objects = InMemoryObjectStore()
    keys = DocumentKeys(_transit_for)
    doc = register(session, "documents/mismatched")
    session.flush()
    keys.mint(session, doc.id, doc.object_key, "_global")  # row names key_id A
    session.commit()
    # the stored object was sealed under a DIFFERENT key_id (a rolled-back write)
    objects.put(doc.object_key, seal(os.urandom(32), "b" * 12, doc.object_key, b"x"))

    found = find_orphans(session, objects, now=LATER)
    assert [k for k, _ in found] == [doc.object_key]

    report = run(_session_factory(session), objects, apply=True, now=LATER)
    assert report["removed"] == [doc.object_key]


def test_sealed_object_with_its_own_row_is_untouched(session):
    objects = InMemoryObjectStore()
    keys = DocumentKeys(_transit_for)
    doc = register(session, "documents/owned")
    session.flush()
    key = keys.mint(session, doc.id, doc.object_key, "_global")
    objects.put(doc.object_key, seal(key.material, key.key_id, doc.object_key, b"x"))
    session.commit()

    assert find_orphans(session, objects, now=LATER) == []
    report = run(_session_factory(session), objects, apply=True, now=LATER)
    assert report["found"] == []
    assert objects.exists(doc.object_key)


def test_a_young_orphan_is_untouched(session):
    objects = InMemoryObjectStore()
    objects.put("documents/young", seal(os.urandom(32), "a" * 12, "documents/young", b"x"))

    assert find_orphans(session, objects) == []  # default `now`: just written
    report = run(_session_factory(session), objects, apply=True)
    assert report["found"] == []
    assert objects.exists("documents/young")


def test_a_legacy_object_is_untouched(session):
    objects = InMemoryObjectStore()
    objects.put("documents/legacy", b"%PDF-1.4 legacy plaintext")

    assert find_orphans(session, objects, now=LATER) == []
    report = run(_session_factory(session), objects, apply=True, now=LATER)
    assert report["found"] == []
    assert objects.exists("documents/legacy")


def test_dry_run_by_default_changes_nothing(session):
    objects = InMemoryObjectStore()
    objects.put("documents/orphan", seal(os.urandom(32), "a" * 12, "documents/orphan", b"x"))
    report = run(_session_factory(session), objects, apply=False, now=LATER)
    assert report["found"] == ["documents/orphan"]
    assert report["applied"] is False
    assert objects.exists("documents/orphan")
