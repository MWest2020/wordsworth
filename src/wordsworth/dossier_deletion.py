# SPDX-License-Identifier: MIT
"""Deleting a dossier (delete-dossiers): the memberships and the dossier row
go; a member document is deleted only when this dossier is its last.

Content-addressing lets one document belong to several dossiers (`dossiers`
spec), so deleting dossier A must not destroy a document dossier B still
holds -- that would let removing one case silently empty another. A member is
therefore deleted (`deletion.delete_document`) only when no other dossier
still holds it; otherwise it keeps its content and only loses the membership
of THIS dossier. Both are "touched": each gets one `dossier-deleted` audit
record, holding the document id, the dossier id, the actor and whether it was
deleted or released -- never a name or a value. The audit table has no home
for a dossier-only fact (`document_id` is a NOT NULL foreign key), so the
record is written against each document it affects, same as
`dossier_events.membership_changed`.

Same guard as document deletion, checked by the caller before this runs. The
dry run walks this exact function (``dry_run=True``) and returns before the
first removal, so its report cannot drift from what the real run does.

Order: a released document is resolved (classified) and its membership row is
removed before the dossier row goes, because the dossier row is the parent of
every membership -- the foreign key would refuse the delete otherwise. A
failed member deletion is a hard error, as in `deletion.py`; the dossier row
is removed only once every member has been handled, so a rerun finishes the
work.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import dossier_events
from .deletion import delete_document
from .models import Dossier, DossierDocument
from .object_store import ObjectStore
from .pipeline import dossiers_of
from .search_index import SearchIndex


class DossierDeletionError(ValueError):
    """A dossier deletion that cannot proceed."""


@dataclass
class DossierDeletionReport:
    """Which documents a dossier deletion deleted outright, and which only
    lost their membership of this dossier. Ids only -- this is exactly what
    the API and CLI report back, and what the `dossier-deleted` records
    confirm, never a name or a value."""

    deleted: list[str] = field(default_factory=list)
    released: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[str]]:
        return {"deleted": self.deleted, "released": self.released}


def _member_elsewhere(session: Session, document_id: UUID, dossier_id: UUID) -> bool:
    """Does this document belong to some OTHER dossier too?"""
    return session.execute(
        select(DossierDocument.dossier_id)
        .where(DossierDocument.document_id == document_id,
               DossierDocument.dossier_id != dossier_id)
        .limit(1)
    ).first() is not None


def delete_dossier(
    session: Session,
    dossier_id: UUID,
    store: ObjectStore,
    index: SearchIndex,
    *,
    actor: str,
    dry_run: bool = False,
) -> DossierDeletionReport:
    """Remove a dossier: its memberships, the dossier row, and the content of
    every member document that belongs to no other dossier. A member that
    belongs to another dossier too keeps its content and loses only this
    membership. ``dry_run`` reports exactly what the real run would do,
    through the same classification and the same `delete_document` dry run,
    without removing anything.

    Raises `DossierDeletionError` for an unknown dossier. Any other failure
    (a member deletion failing) propagates uncaught, same as
    `deletion.delete_document` -- nothing after the failing step has run, and
    (outside ``dry_run``) the caller has not committed, so a later call
    finishes the work.
    """
    dossier = session.get(Dossier, dossier_id)
    if dossier is None:
        raise DossierDeletionError(f"unknown dossier: {dossier_id}")

    member_ids = session.execute(
        select(DossierDocument.document_id)
        .where(DossierDocument.dossier_id == dossier_id)
    ).scalars().all()

    report = DossierDeletionReport()
    for document_id in member_ids:
        if _member_elsewhere(session, document_id, dossier_id):
            report.released.append(str(document_id))
        else:
            delete_document(session, document_id, store, index,
                            actor=actor, dry_run=dry_run)
            report.deleted.append(str(document_id))

    if dry_run:
        return report

    deleted = set(report.deleted)
    for document_id in member_ids:
        released = str(document_id) not in deleted
        membership = session.get(DossierDocument, (dossier_id, document_id))
        if membership is not None:
            session.delete(membership)
            session.flush()
        if released:
            # The document stays indexed under its OTHER dossiers; only this
            # one's scope must stop finding it.
            index.set_dossiers(str(document_id), dossiers_of(session, document_id))
        dossier_events.dossier_deleted(
            session, document_id=document_id, dossier_id=dossier_id,
            actor=actor, released=released)

    session.delete(dossier)
    return report
