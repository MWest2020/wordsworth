# SPDX-License-Identifier: MIT
"""Ingest or processing racing a deletion or a supersession (#452, #462).

`pipeline.register_live` reads the live document without a lock, so before
`ingest` writes the original it locks the row and checks again (`lock_live`).
`process` locks the row the same way before it reads the state
(`lock_for_process`), so a deletion cannot run beside it and leave what it
indexes behind. The lock order is every document writer's: the `documents`
row first, the audit chain's advisory lock after -- a deletion, a
supersession and OCR recovery all lock the row before their first audit
append, and a dossier deletion locks all its members' rows before its first.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import current_state
from .models import Document
from .states import State
from .structured_log import log_ingest_refused

#: How often `ingest` looks the live document up again when the one it found
#: stopped being live before it could lock it. One retry covers a deletion or
#: supersession; a third failure is not a race, it is a refusal.
LIVE_ATTEMPTS = 3


class IngestRaceError(RuntimeError):
    """`ingest` found no document it could lock while it is still live.

    In practice: a document deleted before deletions released the object key
    still holds it. ``public`` is the fixed text a caller may show; the ids
    go to the server log (`log_ingest_refused`), never a filename or a value.
    """

    public = ("no live document for these bytes could be locked; a deleted "
              "document still holding their object key is released by "
              "wordsworth-release-deleted-keys")

    def __init__(self, document_id: UUID, object_key: str):
        self.document_id, self.object_key = document_id, object_key
        log_ingest_refused(document_id=document_id, object_key=object_key,
                           attempts=LIVE_ATTEMPTS)
        super().__init__(f"document {document_id} is not live for {object_key} "
                         f"after {LIVE_ATTEMPTS} attempts; {self.public}")


def lock_live(session: Session, document_id: UUID, object_key: str) -> bool:
    """Lock the document row FOR SHARE and say whether it is still the live
    document for ``object_key``: not superseded, not deleted, key not released.

    FOR SHARE conflicts with the FOR NO KEY UPDATE a deletion or supersession
    takes before it changes anything, so that one either commits first -- and
    the re-read below, a fresh statement under READ COMMITTED, sees it -- or
    waits for this transaction. It does not conflict with the KEY SHARE an
    audit append takes through the foreign key. Held until the caller
    commits, which every caller does right after `ingest`: never across
    extraction or OCR.
    """
    doc = session.execute(
        select(Document).where(Document.id == document_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    ).scalar_one()
    return (doc.object_key == object_key and doc.superseded_by is None
            and current_state(session, document_id) != State.DELETED)


def lock_for_process(session: Session, document_id: UUID) -> Document | None:
    """Lock the document row FOR SHARE before `process` reads its state (#462).

    A deletion takes FOR NO KEY UPDATE before it looks at anything, so it
    either committed first -- `process` then reads `deleted` and does nothing
    -- or waits for `process` to commit and then removes what it wrote,
    index entry and text included. Held for the whole `process` call, which
    is one transaction: the deletion waited for its chain lock that long
    already, but then only after it had looked for an index entry not yet
    written. ``None`` for an unknown document, as `session.get`.
    """
    return session.get(Document, document_id, populate_existing=True,
                       with_for_update={"read": True})
