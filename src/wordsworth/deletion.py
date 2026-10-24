# SPDX-License-Identifier: MIT
"""Deleting a document (document-deletion).

The row stays; the content goes. `audit_records.document_id` is a non-null
foreign key and the audit table has no UPDATE/DELETE, so removing the
`documents` row would either break the trail or require deleting audit
records — the one thing this system never does (same reason a superseded copy
keeps its row, see `supersession.py`). Deletion therefore removes everything
*about the content* (the stored object, the stored text, the pseudonyms, the
mappings, the index entry and the grants) and leaves the row and its audit
records. The transition to `deleted` and its audit record are written in the
same transaction as the removal, holding ids and counts only -- never a value.

Order and failure: the index entry and the object bytes go first, in that
order, exactly as `supersession.py` retires a copy "out of the index first" --
each is an external side effect the database transaction cannot roll back, and
leaving either behind would mean a `deleted` record over content that is still
searchable or still stored. The database-only work (text, pseudonyms, mappings,
grants, the audit record) follows inside the caller's transaction. Every step
is idempotent (deleting what is already gone is a no-op), so a failure at any
point leaves a state a rerun finishes -- it never writes the `deleted` record
over a removal that did not complete.

The mapping store is global (`mapping_store.py`: "one value must yield one
token everywhere"), so a pseudonym can be shared by more than one document. A
document's `document_pseudonyms` rows are always its own and always removed;
the shared `pii_mappings` row underneath is removed only when no other
document still references that pseudonym -- removing it while another document
needs it would make that document's reveal path try to decrypt nothing.
Similarly `object_key` is content-addressed and a superseded copy keeps its
former key (one-document-per-object), so the stored object is removed only
when no other, still-existing document row claims the same key.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import current_state
from .models import Document, DocumentPseudonym, DocumentText, GrantRecord, PiiMapping
from .object_store import ObjectStore
from .pipeline import transition
from .search_index import SearchIndex
from .states import State


class DeletionError(ValueError):
    """A deletion that cannot proceed."""


@dataclass
class DeletionCounts:
    """How many of each kind a deletion removed (or, dry-run, would remove).
    Ids and counts only -- this is exactly what the `deleted` audit record
    carries, never a value, a filename or a token."""

    object: int = 0
    text: int = 0
    pseudonyms: int = 0
    mappings: int = 0
    index_entries: int = 0
    grants: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"object": self.object, "text": self.text,
                "pseudonyms": self.pseudonyms, "mappings": self.mappings,
                "index_entries": self.index_entries, "grants": self.grants}


def _object_claimed_elsewhere(session: Session, document_id: UUID, object_key: str) -> bool:
    """Does some OTHER, not-yet-deleted document row still claim this object
    key? A superseded copy keeps its former key (one-document-per-object), so
    more than one row can point at the same bytes; removing them under one row
    must not take them out from under another that still needs them."""
    others = session.execute(
        select(Document.id).where(Document.object_key == object_key,
                                  Document.id != document_id)
    ).scalars().all()
    return any(current_state(session, other) != State.DELETED for other in others)


def delete_document(
    session: Session,
    document_id: UUID,
    store: ObjectStore,
    index: SearchIndex,
    *,
    actor: str,
    dry_run: bool = False,
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
    """
    doc = session.get(Document, document_id)
    if doc is None:
        raise DeletionError(f"unknown document: {document_id}")

    counts = DeletionCounts()

    counts.index_entries = int(index.exists(str(document_id)))
    if not dry_run and counts.index_entries:
        index.delete(str(document_id))

    object_removable = (
        store.exists(doc.object_key)
        and not _object_claimed_elsewhere(session, document_id, doc.object_key)
    )
    counts.object = int(object_removable)
    if not dry_run and object_removable:
        store.delete(doc.object_key)

    text_row = session.get(DocumentText, document_id)
    counts.text = int(text_row is not None)
    if not dry_run and text_row is not None:
        session.delete(text_row)

    pseudonyms = session.execute(
        select(DocumentPseudonym.pseudonym)
        .where(DocumentPseudonym.document_id == document_id)
    ).scalars().all()
    counts.pseudonyms = len(pseudonyms)
    for pseudonym in pseudonyms:
        orphaned = session.execute(
            select(DocumentPseudonym.document_id)
            .where(DocumentPseudonym.pseudonym == pseudonym,
                   DocumentPseudonym.document_id != document_id)
            .limit(1)
        ).first() is None
        if orphaned and session.get(PiiMapping, pseudonym) is not None:
            counts.mappings += 1
        if not dry_run:
            session.execute(
                sa_delete(DocumentPseudonym)
                .where(DocumentPseudonym.document_id == document_id,
                       DocumentPseudonym.pseudonym == pseudonym))
            if orphaned:
                mapping_row = session.get(PiiMapping, pseudonym)
                if mapping_row is not None:
                    session.delete(mapping_row)

    grant_rows = session.execute(
        select(GrantRecord).where(GrantRecord.document_id == document_id)
    ).scalars().all()
    counts.grants = len(grant_rows)
    if not dry_run:
        for row in grant_rows:
            session.delete(row)

    if dry_run:
        return counts

    session.flush()
    transition(session, document_id, State.DELETED, step="delete",
              payload={"actor": actor, **counts.as_dict()})
    return counts
