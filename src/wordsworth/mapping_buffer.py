# SPDX-License-Identifier: MIT
"""The buffer behind `PostgresMappingStore.put`, and the one way out of it.

`put` only buffers a `pii_mappings` row on the session; `write_pending`
stores the buffer under the audit chain lock, in pseudonym order
(`docs/reference/lock-order.md`). Rows inserted in text order, before the
chain lock, made two runs minting the same values wait in a circle (#465,
#504). Nothing writes the buffer implicitly: an outermost commit with rows
still in it raises `UnwrittenMappings`, and the end of the outermost
transaction empties it (#505 review)."""
from __future__ import annotations

from sqlalchemy import event, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from . import audit
from .models import PiiMapping

#: `Session.info` key: the rows `put` buffered and `write_pending` has not
#: stored yet, by pseudonym. On the session, not on the store, because the
#: writer (`pseudonym_registry.link`) has the session and not the store the
#: anonymizer was built on.
PENDING = "pii_mappings_pending"


class UnwrittenMappings(RuntimeError):
    """A transaction is committing while `put` rows are still buffered."""


class WriteInSavepoint(RuntimeError):
    """`write_pending` was called inside a savepoint."""


def write_pending(session: Session, only: set[str] | None = None) -> None:
    """Store the buffered mapping rows and hold them until the transaction
    ends. Under the audit chain lock, taken here (it flushes first), in
    pseudonym order: `INSERT ... ON CONFLICT DO NOTHING`, then FOR KEY SHARE.

    A deletion removes a mapping no document is linked to, and decides that
    under the same lock (`deletion_mappings`), so a row stored or found here
    cannot go before this transaction's links commit (#465). Every insert
    into `pii_mappings` is made under the chain lock too, so an insert here
    never waits for another one. `reencrypt` is the exception: it updates
    rows without the chain lock (lock-order.md, Known exceptions), and an
    insert here can wait for it.

    The FOR KEY SHARE hold is defence in depth. Every deleter decides under
    the chain lock this transaction holds until it ends, so that lock alone
    keeps the rows; the hold makes a DELETE outside that rule wait rather
    than succeed. It covers rows of ``only`` that were not buffered too (the
    backfill links tokens it read from stored text and put nothing).

    ``only``: the pseudonyms the caller links (the tokens of the text it
    keeps). Buffered rows outside it are dropped, not stored -- nothing would
    refer to them. Without ``only`` everything buffered is stored. Refused
    inside a savepoint: rolling that back would take the stored rows and the
    chain lock with it, the buffer already emptied."""
    if session.in_nested_transaction():
        raise WriteInSavepoint("mapping_buffer.write_pending inside a savepoint: "
                               "a rollback of it would drop the rows it stores")
    pending = session.info.pop(PENDING, {})
    names = sorted(pending if only is None else only)
    audit.lock_chain(session)
    if not names:
        return
    rows = [pending[name] for name in names if name in pending]
    if rows:
        session.execute(pg_insert(PiiMapping)
                        .on_conflict_do_nothing(index_elements=["pseudonym"]), rows)
    session.execute(select(PiiMapping.pseudonym)
                    .where(PiiMapping.pseudonym.in_(names))
                    .order_by(PiiMapping.pseudonym)
                    .with_for_update(key_share=True, read=True))


@event.listens_for(Session, "before_commit")
def _nothing_buffered_at_commit(session: Session) -> None:
    """Refuse a commit that would lose a `put`: the caller forgot
    `write_pending`. Loud on purpose: nothing is written and no lock is
    taken here, so the lock order stays where the code shows it. Only the
    outermost commit: SQLAlchemy fires this for a savepoint release too."""
    if session.in_nested_transaction():
        return
    pending = session.info.get(PENDING)
    if pending:
        raise UnwrittenMappings(
            f"{len(pending)} pii_mappings rows were put and never written; "
            "call mapping_buffer.write_pending(session) before the commit")


@event.listens_for(Session, "after_transaction_end")
def _drop_at_end(session: Session, transaction) -> None:
    """The buffer lives as long as the outermost transaction: a commit got
    here with nothing buffered (above), a rollback or a `close` stores
    nothing. A savepoint's end is not it -- `register_live` and
    `dossiers.add` roll one back on a lost race, and the puts made before
    it belong to the run that goes on."""
    if transaction.parent is None:
        session.info.pop(PENDING, None)
