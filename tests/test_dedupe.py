# SPDX-License-Identifier: MIT
"""`wordsworth-dedupe` (one-document-per-object, release 1).

Production on 2026-09-24: 173 copies over 93 objects. The command has to find
exactly those, change nothing unless told to, and refuse when the numbers it
finds are not the numbers it was sent for.
"""
import pytest

from wordsworth import dossiers
from wordsworth.dedupe import main, plan, run
from wordsworth.models import Document
from wordsworth.pipeline import current_state, register
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State


def _corpus(session_factory, index):
    """Object X three times, object Y twice, object Z once; every copy in one dossier."""
    ids = {}
    with session_factory() as s:
        d = dossiers.ensure(s, "Woo")
        for name, n in (("x", 3), ("y", 2), ("z", 1)):
            key = "documents/" + name * 64
            ids[name] = []
            for _ in range(n):
                doc = register(s, key)
                s.flush()
                dossiers.add(s, d.id, doc.id, actor="t")
                index.index(str(doc.id), f"tekst {name}", key)
                ids[name].append(doc.id)
        s.commit()
    return ids


def test_the_oldest_copy_survives(session_factory):
    ids = _corpus(session_factory, InMemoryIndex())
    with session_factory() as s:
        groups = {key[-1]: (survivor, copies) for key, survivor, copies in plan(s)}
    assert set(groups) == {"x", "y"}
    assert groups["x"] == (ids["x"][0], ids["x"][1:])
    assert groups["y"] == (ids["y"][0], ids["y"][1:])


def test_a_dry_run_changes_nothing(session_factory):
    index = InMemoryIndex()
    ids = _corpus(session_factory, index)
    report = run(session_factory, index, apply=False, expect={})
    assert report["found"] == {"objects": 2, "copies": 3, "memberships": 3}
    assert report["applied"] is False
    with session_factory() as s:
        assert all(s.get(Document, i).superseded_by is None for i in ids["x"])
    assert len(index.search("tekst")) == 6


def test_unexpected_numbers_stop_it_before_anything_changes(session_factory):
    index = InMemoryIndex()
    ids = _corpus(session_factory, index)
    report = run(session_factory, index, apply=True,
                 expect={"copies": 173, "memberships": 3})
    assert report["refused"] == {"copies": {"expected": 173, "found": 3}}
    assert report["applied"] is False
    with session_factory() as s:
        assert current_state(s, ids["x"][1]) == State.REGISTERED


def test_apply_retires_every_copy_and_a_rerun_finds_none(session_factory):
    index = InMemoryIndex()
    ids = _corpus(session_factory, index)
    report = run(session_factory, index, apply=True,
                 expect={"copies": 3, "memberships": 3, "index_entries": 3})
    assert report["done"] == {"superseded": 3, "moved": 0, "removed": 3,
                              "index_entries": 3}
    assert "index_entries_differ" not in report
    with session_factory() as s:
        for name in ("x", "y"):
            survivor, *copies = ids[name]
            assert all(s.get(Document, c).superseded_by == survivor for c in copies)
            assert current_state(s, survivor) == State.REGISTERED
    assert sorted(h.object_key[-1] for h in index.search("tekst")) == ["x", "y", "z"]
    again = run(session_factory, index, apply=True,
                expect={"copies": 0, "memberships": 0})
    assert again["found"]["copies"] == 0 and again["done"]["superseded"] == 0


def test_a_different_index_count_is_reported(session_factory):
    index = InMemoryIndex()
    ids = _corpus(session_factory, index)
    index.delete(str(ids["x"][2]))                  # one copy was never indexed
    report = run(session_factory, index, apply=True,
                 expect={"copies": 3, "memberships": 3, "index_entries": 3})
    assert report["index_entries_differ"] == {"expected": 3, "removed": 2}


def test_apply_without_the_expected_numbers_is_refused():
    with pytest.raises(SystemExit):
        main(["--apply"])
