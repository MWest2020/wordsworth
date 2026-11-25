# SPDX-License-Identifier: MIT
"""`audit.lock_chain` flushes the session before it takes the chain lock
(`docs/reference/lock-order.md`, #466).

The lock is a plain statement, and a plain statement does not autoflush. A
row change still pending in the session would reach the database after the
chain lock, at the next flush: a row lock asked for under the chain lock,
the wrong way round. Against a deletion -- row first, chain lock after --
that is a deadlock."""
from __future__ import annotations

from sqlalchemy import select, text

from race_setup import run, wait_for_a_lock_waiter
from wordsworth import audit
from wordsworth.models import Document
from wordsworth.pipeline import register


def test_a_pending_row_change_is_flushed_before_the_chain_lock(session_factory):
    with session_factory() as s:
        doc_id = register(s, "documents/" + "ef" * 32).id
        s.commit()
    errors = {}

    def writer():
        with session_factory() as w:
            w.execute(text("SET lock_timeout = '10s'"))
            w.get(Document, doc_id).filename = "renamed"  # pending, not flushed
            audit.lock_chain(w)
            w.commit()

    with session_factory() as holder:  # a deletion's order: the row, then the chain
        holder.execute(text("SET lock_timeout = '10s'"))
        holder.execute(select(Document).where(Document.id == doc_id)
                       .with_for_update(key_share=True))
        thread = run(errors, "writer", writer)
        try:
            wait_for_a_lock_waiter(session_factory)  # the writer waits for the row
            # The writer must not hold the chain lock while it waits for the row.
            audit.lock_chain(holder)
            holder.commit()
        finally:
            thread.join(30)

    assert not errors, errors
    with session_factory() as s:
        assert s.get(Document, doc_id).filename == "renamed"
