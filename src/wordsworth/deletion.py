# SPDX-License-Identifier: MIT
"""Deleting a document (document-deletion).

The row stays; the content goes. `audit_records.document_id` is a non-null
foreign key and the audit table has no UPDATE/DELETE, so removing the row would
break the trail or require deleting audit records — the one thing this system
never does (as a superseded copy keeps its row, `supersession.py`). Deletion
removes everything *about the content* (object, text, pseudonyms, mappings,
index entry, grants, and the cached redacted PDFs, box map and summary, see
`deletion_renders.py`) and keeps the row and its audit records. The `deleted`
record is written in the same transaction: ids and counts, never a value.

Order and failure: the cached renders are listed first (`deletion_renders`), so
a listing failure removes nothing; then the index entry and the object bytes go,
in that order, as `supersession.py` retires a copy "out of the index first" --
side effects the transaction cannot roll back, and leaving either behind would
mean a `deleted` record over content still searchable or stored. The DB-only
work (text, pseudonyms, mappings, grants, the record) follows in the caller's
transaction. Every step is idempotent, so a failure at any point leaves a state
a rerun finishes, never a `deleted` record over an incomplete removal.

The mapping store is global (`mapping_store.py`: "one value must yield one
token everywhere"), so a pseudonym can be shared by more than one document. A
document's `document_pseudonyms` rows are always its own and always removed;
the shared `pii_mappings` row underneath is removed only when no other
document still references that pseudonym -- removing it while another document
needs it would make that document's reveal path try to decrypt nothing
(`deletion_mappings.py`, which decides it under the audit chain lock, #465).
Similarly `object_key` is content-addressed and a superseded copy keeps its
former key (one-document-per-object), so the stored object is removed only
when no other, still-existing document row claims the same key.

Deleting also releases the object key itself (deleted-document-releases-
object-key): a deleted document's row no longer counts as *the* live document
for its bytes (`live_document_for`, the partial unique index), so the same
bytes can be ingested again. In the same transaction as the `deleted` record,
`object_key` becomes the placeholder `deleted/<document_id>` -- unique by
construction, never equal to a content-addressed key -- and the former key is
recorded in that record as `released_object_key` (an id, not a value). The
object-removal check above runs against the former key, before the release.

Deleting a sealed original also destroys its data key (`deletion_keys.py`):
`doomed` locks the row and its copies (#452: no ingest writes the object back)
and picks the keys first; key rows go after the object, in this transaction.
A rerun over an already-deleted document that finds a key records `destroy-key`.

Deleting a document recovered by OCR also removes its original scan object
(`deletion_scans.py`, #454): the scan is named only in the document's
recovering `ocr` audit record, never overwritten by `recover`, and goes with
the deletion under the same claim the object and the key already use --
unless another document that is not deleted still claims it. The scan is
removed right after the main object, before the DB-only work; a rerun over an
already-deleted document that still finds one removes it and records
`remove-original-scan`.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import deletion_keys, deletion_mappings, deletion_scans
from .audit import current_state
from .document_keys import DocumentKeys
from .models import Document, DocumentText, GrantRecord
from .deletion_renders import DeletionCounts, plan_renders  # re-exported
from .object_store import ObjectStore
from .pipeline import transition
from .search_index import SearchIndex
from .states import State

DELETED_KEY_PREFIX = "deleted/"


def released_object_key(document_id: UUID) -> str:
    """The placeholder a deleted document's `object_key` becomes: unique by
    construction (so the partial unique index never refuses it) and never
    equal to a content-addressed key (`documents/<sha256>`)."""
    return f"{DELETED_KEY_PREFIX}{document_id}"


class DeletionError(ValueError):
    """A deletion that cannot proceed."""


def delete_document(
    session: Session,
    document_id: UUID,
    store: ObjectStore,
    index: SearchIndex,
    *,
    actor: str,
    dry_run: bool = False,
    keys: DocumentKeys | None = None,
) -> DeletionCounts:
    """Remove a document's content, or (``dry_run``) only report what would be
    removed. Idempotent: an already-deleted document's content is already gone,
    so a rerun finds nothing left to do and (outside ``dry_run``) writes no
    second `deleted` record -- `transition` is itself a no-op when the state
    does not change.

    Raises `DeletionError` for an unknown document; any other failure (the
    index unreachable, a database error) propagates uncaught -- a hard error,
    never a silent partial deletion. Nothing after the failing step has run,
    and (outside ``dry_run``) the caller has not committed, so the document
    stays in its previous state and a later call finishes the work.
    ``keys`` only evicts its unwrap cache; key rows go with or without it.
    """
    doc = session.get(Document, document_id)
    if doc is None:
        raise DeletionError(f"unknown document: {document_id}")

    counts = DeletionCounts()
    former_key, doomed = deletion_keys.doomed(session, document_id, lock=not dry_run)
    doc = session.get(Document, document_id, populate_existing=True)
    already_deleted = current_state(session, document_id) == State.DELETED

    counts.index_entries = int(index.exists(str(document_id)))
    renders = plan_renders(session, document_id, store, counts)  # reads only
    if not dry_run and counts.index_entries:
        index.delete(str(document_id))

    object_removable = (
        store.exists(former_key)
        and not deletion_keys._object_claimed_elsewhere(session, document_id, former_key)
    )
    counts.object = int(object_removable)
    if not dry_run and object_removable:
        store.delete(former_key)

    scans = deletion_scans.plan(session, document_id, former_key, store)
    counts.original_scan = len(scans)
    if not dry_run:
        for scan_key in scans:
            store.delete(scan_key)

    renders.apply(session, store, counts, actor=actor, dry_run=dry_run)

    text_row = session.get(DocumentText, document_id)
    counts.text = int(text_row is not None)
    if not dry_run and text_row is not None:
        session.delete(text_row)

    grant_rows = session.execute(
        select(GrantRecord).where(GrantRecord.document_id == document_id)
    ).scalars().all()
    counts.grants = len(grant_rows)
    if not dry_run:
        for row in grant_rows:
            session.delete(row)

    counts.keys_destroyed = len(doomed)
    deletion_mappings.remove(session, document_id, counts, dry_run=dry_run)
    if dry_run:
        return counts

    session.flush()
    deletion_keys.destroy(session, doomed)
    if keys is not None:
        keys.evict(doomed)
    if already_deleted:
        if scans:
            deletion_scans.record_rerun(session, document_id, actor=actor,
                                        original_scan=len(scans))
        if doomed:
            deletion_keys.record_rerun(session, document_id, actor=actor,
                                       keys_destroyed=len(doomed))
        return counts
    payload: dict = {"actor": actor, **counts.as_dict(),
                     "released_object_key": former_key}
    doc.object_key = released_object_key(document_id)
    transition(session, document_id, State.DELETED, step="delete", payload=payload)
    return counts
