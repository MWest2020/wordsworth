# SPDX-License-Identifier: MIT
"""The pseudonyms and mappings a deletion removes (`deletion.py`, #465).

A document's `document_pseudonyms` rows are its own and always go. The
`pii_mappings` row underneath is shared -- one value is one token everywhere
(`mapping_store.py`) -- and goes only when no other document is linked to that
pseudonym.

"No other document" is decided under the audit chain lock. Another document
being anonymised right now has `put` the same value (finding the row, taking
no lock) and has not committed its own links yet; a check without the lock did
not see them and removed the row, so that document's token could never be
revealed. `pseudonym_registry.link` takes the same lock before it links, so
either its links are committed and the check below sees them, or it links
after this deletion committed and stores the mapping again
(`mapping_store.pin`).

Lock order (`docs/reference/lock-order.md`): the document rows and key rows
are held already (`deletion_keys.doomed`); pending deletes are flushed before
the chain lock, so no other row lock is first asked for under it; the mapping
rows come last, in pseudonym order. A dry run takes no lock.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit, mapping_store
from .deletion_renders import DeletionCounts
from .models import DocumentPseudonym, PiiMapping


def remove(session: Session, document_id: UUID, counts: DeletionCounts, *,
           dry_run: bool) -> None:
    """Count, and outside ``dry_run`` remove, this document's pseudonym links
    and every mapping left without a link. Sets ``counts.pseudonyms`` and
    ``counts.mappings``."""
    pseudonyms = session.execute(
        select(DocumentPseudonym.pseudonym)
        .where(DocumentPseudonym.document_id == document_id)
        .order_by(DocumentPseudonym.pseudonym)
    ).scalars().all()
    counts.pseudonyms = len(pseudonyms)
    if not pseudonyms:
        return
    if not dry_run:
        session.flush()
        audit.lock_chain(session)
    linked_elsewhere = set(session.execute(
        select(DocumentPseudonym.pseudonym)
        .where(DocumentPseudonym.pseudonym.in_(pseudonyms),
               DocumentPseudonym.document_id != document_id)
    ).scalars().all())
    orphans = [p for p in pseudonyms if p not in linked_elsewhere]
    counts.mappings = len(session.execute(
        select(PiiMapping.pseudonym).where(PiiMapping.pseudonym.in_(orphans))
    ).scalars().all()) if orphans else 0
    if dry_run:
        return
    session.execute(sa_delete(DocumentPseudonym)
                    .where(DocumentPseudonym.document_id == document_id))
    mapping_store.remove_orphans(session, orphans)
