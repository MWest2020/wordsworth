# SPDX-License-Identifier: MIT
"""A `put` is buffered on the session and written only by `write_pending`,
under the audit chain lock (`docs/reference/lock-order.md`). Nothing writes
it implicitly and nothing drops it silently: a commit that would lose a
buffered row raises `UnwrittenMappings`, and only the end of the outermost
transaction empties the buffer (#505 review)."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from reanon_helpers import BSN, new_key_provider
from wordsworth import pseudonym_registry
from wordsworth.mapping_store import (PostgresMappingStore, UnwrittenMappings,
                                      write_pending)
from wordsworth.models import Document, DocumentPseudonym, PiiMapping
from wordsworth.pipeline import register
from wordsworth.pseudonymizer import Pseudonymizer

OTHER_BSN = "234567892"  # valid (elfproef)


def _advisory_locks(session) -> int:
    return session.execute(text(
        "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' "
        "AND pid = pg_backend_pid()")).scalar_one()


def _stored(session) -> list[str]:
    return session.execute(select(PiiMapping.pseudonym)
                           .order_by(PiiMapping.pseudonym)).scalars().all()


def test_a_put_is_buffered_and_a_commit_that_would_lose_it_raises(session_factory):
    """`put` touches no row and takes no lock; `write_pending` stores what is
    buffered under the chain lock; a commit with rows still buffered raises
    instead of writing or losing them; a rollback drops them."""
    kp = new_key_provider()
    with session_factory() as s, session_factory() as other:
        pseudonymizer = Pseudonymizer(kp, PostgresMappingStore(s))
        first = pseudonymizer.pseudonym("bsn", BSN)
        assert PostgresMappingStore(s).get(first) is not None  # read your own put
        assert _stored(s) == []
        assert _advisory_locks(s) == 0
        write_pending(s)
        assert _advisory_locks(s) == 1
        s.commit()
        assert _stored(other) == [first]

        pseudonymizer.pseudonym("bsn", OTHER_BSN)
        with pytest.raises(UnwrittenMappings, match="write_pending"):
            s.commit()
        assert _advisory_locks(s) == 0  # nothing written, nothing locked
        s.rollback()
        s.commit()  # the rollback dropped the buffer: nothing left to refuse
        other.rollback()
        assert _stored(other) == [first]


def test_a_savepoint_neither_drops_nor_writes_the_buffered_puts(session_factory):
    """SQLAlchemy fires the commit and rollback events for a savepoint too.
    `register_live` and `dossiers.add` open one and roll it back on a lost
    race, in the middle of a run that has already `put`. The rows must still
    be buffered when the run links -- not dropped by the rollback, and not
    written (nor the chain lock taken) by the release."""
    kp = new_key_provider()
    with session_factory() as s, session_factory() as other:
        doc_id = register(s, "documents/" + "ab" * 32).id
        s.commit()  # its audit record took the chain lock; released here
        token = Pseudonymizer(kp, PostgresMappingStore(s)).pseudonym("bsn", BSN)
        assert _advisory_locks(s) == 0

        with pytest.raises(IntegrityError):
            with s.begin_nested():  # rolled back: a second row with this id
                s.add(Document(id=doc_id, object_key="documents/" + "cd" * 32))
                s.flush()
        with s.begin_nested():  # released: not the run's commit
            s.execute(text("SELECT 1"))

        assert _advisory_locks(s) == 0  # the release took no chain lock
        assert _stored(s) == []  # and wrote nothing, not even in this transaction
        assert PostgresMappingStore(s).get(token) is not None  # still buffered

        assert pseudonym_registry.link(s, doc_id, f"BSN {token}") == 1
        s.commit()
        assert _stored(other) == [token]
        assert other.get(DocumentPseudonym, (doc_id, token)) is not None


def test_write_pending_is_refused_inside_a_savepoint(session_factory):
    """Rolling the savepoint back would take the stored rows (and the chain
    lock) with it after the buffer was emptied. Refused before anything is
    taken from the buffer."""
    kp = new_key_provider()
    with session_factory() as s, session_factory() as other:
        token = Pseudonymizer(kp, PostgresMappingStore(s)).pseudonym("bsn", BSN)
        with s.begin_nested():
            with pytest.raises(RuntimeError, match="savepoint"):
                write_pending(s)
        assert _advisory_locks(s) == 0
        write_pending(s)
        s.commit()
        assert _stored(other) == [token]


def test_a_closed_session_leaves_no_buffer_behind(session_factory):
    """`close` ends the transaction without a rollback event; the buffer must
    end with it, or a reused session refuses (or stores) a dead run's rows."""
    kp = new_key_provider()
    s = session_factory()
    try:
        Pseudonymizer(kp, PostgresMappingStore(s)).pseudonym("bsn", BSN)
        s.close()
        s.commit()  # nothing buffered any more
        assert s.scalar(select(func.count()).select_from(PiiMapping)) == 0
    finally:
        s.close()
