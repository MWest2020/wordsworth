# SPDX-License-Identifier: MIT
"""The row locks a dossier deletion takes before it changes anything (#462;
widened by `delete-removes-original-scan`, #454).

Every document writer locks the `documents` row first and takes the audit
chain's advisory lock after (`ingest_lock.py`). A dossier deletion deletes
several members in one transaction, so locking each member's row only when
`delete_document` reaches it breaks that order: member 1's `deleted` record
takes the chain lock and keeps it until commit, then member 2's row lock
waits on a `process` or `ingest` holding member 2's row FOR SHARE while it
waits for the chain lock -- `DeadlockDetected`.

`lock_members` therefore locks, in one statement ordered by id, the row of
every member plus every row sharing one of their object keys (a superseded
copy, or a copy or re-ingest of a member's scan), the object key of a key row
carrying their id, or a recovering `ocr` record naming one of those keys as
its scan (the member's own row, when the member is the scan's claimant and
some other document shares its own object key or key row). That is the set
crypto-shred's `deletion_keys.doomed` locks per member; taken any later, a
copy with a lower id than its member deadlocks with a concurrent deletion of
that copy. NO KEY UPDATE, the mode `delete_document` takes: an audit append's
KEY SHARE is not blocked, and `delete_document`'s own lock is then
re-entrant.
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import deletion_scans
from .document_keys import DocumentKeyRecord
from .models import AuditRecord, Document
from .states import State


def _object_keys(session: Session, document_ids: Sequence[UUID]) -> set[str]:
    """The object keys of these rows, of the key rows carrying their id, and
    of their original scans (`deletion_scans.scan_keys`)."""
    own = session.execute(select(Document.object_key)
                          .where(Document.id.in_(document_ids))).scalars().all()
    sealed = session.execute(
        select(DocumentKeyRecord.object_key)
        .where(DocumentKeyRecord.document_id.in_(document_ids))).scalars().all()
    scans = deletion_scans.scan_keys(session, document_ids)
    return set(own) | set(sealed) | scans


def lock_members(session: Session, document_ids: Sequence[UUID]) -> None:
    """Lock the rows of ``document_ids``, of every row sharing their object
    keys, and of every row with a recovering `ocr` record naming one of
    those keys as its scan, FOR NO KEY UPDATE, ordered by id. Reads the keys
    again under the lock and repeats while they changed before it (a
    deletion that committed while this one waited released its key, a
    recovery repointed it); once the rows are held, their keys cannot change
    again. Never called by a dry run."""
    if not document_ids:
        return
    locked_for = None
    while True:
        keys = _object_keys(session, document_ids)
        if keys == locked_for:
            return
        session.execute(
            select(Document.id)
            .where(or_(Document.id.in_(document_ids),
                       Document.object_key.in_(sorted(keys)),
                       Document.id.in_(
                           select(AuditRecord.document_id).where(
                               AuditRecord.step == "ocr",
                               AuditRecord.to_state == State.EXTRACTABLE.value,
                               AuditRecord.payload["old_object_key"].astext.in_(sorted(keys))))))
            .order_by(Document.id)
            .with_for_update(key_share=True)
        ).all()
        locked_for = keys
