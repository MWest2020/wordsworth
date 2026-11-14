# SPDX-License-Identifier: MIT
"""#462: which rows a dossier deletion locks before it starts -- every
member, deleted or only released, and every row sharing one of their object
keys (a superseded copy), or a recovering `ocr` record naming one of those
keys as its scan (`delete-removes-original-scan`, #454) -- and that a dry
run locks nothing. The races this prevents are in
`test_dossier_deletion_deadlocks.py`."""
from __future__ import annotations

import pytest
from psycopg.errors import LockNotAvailable
from sqlalchemy import insert, select, text
from sqlalchemy.exc import OperationalError

from scan_setup import recover_now

from wordsworth import dossiers
from wordsworth.audit import current_state
from wordsworth.dossier_deletion import delete_dossier
from wordsworth.models import Document, Dossier
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import ingest, register
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State
from wordsworth.supersession import supersede


def _try_lock(session_factory, document_id) -> bool:
    with session_factory() as probe:
        try:
            probe.execute(select(Document.id).where(Document.id == document_id)
                          .with_for_update(key_share=True, nowait=True)).all()
            return True
        except OperationalError as exc:
            assert isinstance(exc.orig, LockNotAvailable)
            return False
        finally:
            probe.rollback()


def _dossier(session):
    """Dossier `zaak` with an exclusive member (plus a superseded copy that
    shares its object key), a member another dossier holds too, and an
    unrelated document."""
    key_a, key_s = "documents/" + "a1" * 32, "documents/" + "c3" * 32
    zaak, andere = dossiers.ensure(session, "zaak"), dossiers.ensure(session, "andere")
    a, shared = register(session, key_a), register(session, key_s)
    other = register(session, "documents/" + "d4" * 32)
    session.flush()
    copy_id = session.execute(insert(Document).values(
        object_key=key_a, superseded_by=a.id).returning(Document.id)).scalar_one()
    for dossier, doc in ((zaak, a), (zaak, shared), (andere, shared)):
        dossiers.add(session, dossier.id, doc.id, actor="t")
    session.commit()
    return zaak.id, a.id, copy_id, shared.id, other.id


def test_the_lock_covers_every_member_and_its_copies(session_factory):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        zaak, a, copy_id, shared, other = _dossier(s)
        report = delete_dossier(s, zaak, store, index, actor="t")
        # Not committed: the locks are still held.
        assert not _try_lock(session_factory, a)
        assert not _try_lock(session_factory, copy_id)
        assert not _try_lock(session_factory, shared)
        assert _try_lock(session_factory, other)
        s.commit()
    assert (report.deleted, report.released) == ([str(a)], [str(shared)])


@pytest.mark.parametrize("held", ["member", "copy"])
def test_a_dry_run_takes_no_lock(session_factory, held):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        zaak, a, copy_id, shared, _ = _dossier(s)
    with session_factory() as holder:
        holder.execute(select(Document.id).where(
            Document.id == (a if held == "member" else copy_id)).with_for_update())
        with session_factory() as s:
            s.execute(text("SET lock_timeout = '2s'"))
            report = delete_dossier(s, zaak, store, index, actor="t", dry_run=True)
            s.rollback()
        holder.rollback()
    assert (report.deleted, report.released) == ([str(a)], [str(shared)])
    with session_factory() as s:
        assert s.get(Dossier, zaak) is not None
        assert current_state(s, a) != State.DELETED


def test_the_lock_covers_a_recovered_members_scan_and_its_copy(
        legacy_copies, scanned_pdf):
    """A recovered member A (scan S) and a copy C, outside the dossier, whose
    `object_key` is S: a dry run locks nothing, but while the real deletion
    holds its locks, a concurrent attempt to lock C's row fails."""
    store = InMemoryObjectStore()
    with legacy_copies() as s:
        zaak = dossiers.ensure(s, "zaak")
        survivor = ingest(s, store, scanned_pdf)
        s.commit()
        scan_key = survivor.object_key
        copy = register(s, scan_key)
        s.commit()
        supersede(s, copy.id, survivor.id, actor="t")
        s.commit()
        recover_now(s, store, survivor.id)
        assert copy.object_key == scan_key
        dossiers.add(s, zaak.id, survivor.id, actor="t")
        s.commit()
        zaak_id, survivor_id, copy_id = zaak.id, survivor.id, copy.id

    with legacy_copies() as holder:
        holder.execute(select(Document.id).where(Document.id == copy_id)
                       .with_for_update())
        with legacy_copies() as s:
            s.execute(text("SET lock_timeout = '2s'"))
            dry = delete_dossier(s, zaak_id, store, InMemoryIndex(), actor="t",
                                 dry_run=True)
            s.rollback()
        holder.rollback()
    # C still claims S (it is not deleted), so neither run removes it --
    # the lock below is taken regardless of that outcome.
    assert dry.deleted == [str(survivor_id)] and dry.original_scan == 0

    with legacy_copies() as s:
        report = delete_dossier(s, zaak_id, store, InMemoryIndex(), actor="t")
        # Not committed: the locks are still held.
        assert not _try_lock(legacy_copies, copy_id)
        s.commit()
    assert report.deleted == [str(survivor_id)] and report.original_scan == 0
    with legacy_copies() as s:
        assert current_state(s, survivor_id) == State.DELETED
