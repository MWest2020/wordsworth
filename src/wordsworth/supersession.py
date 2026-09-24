# SPDX-License-Identifier: MIT
"""Retiring a copy of an object that already is a document (one-document-per-object).

`object_key` is the sha256 of a document's bytes, so two documents with one key
are one object twice. On 2026-09-24 production held 173 such copies, all from
three ingest runs of one batch in August. A copy cannot be deleted: every audit
record points at its document and the trail is append-only. So it is retired:

1. **Out of the index first.** The index is not transactional; if this step
   succeeds and the rest fails, the copy is merely unsearchable while the
   survivor, with the same bytes, still is -- and a rerun finishes the job.
   The other order would leave a retired document searchable.
2. **Its dossiers pass to the survivor**, then the copy leaves them. Both are
   the ordinary recorded acts (`dossiers.add` / `dossiers.remove`), so no
   dossier loses a document it contained and every change leaves a trace.
3. **The state `superseded`** in the audit trail, and the pointer
   `superseded_by`, in the caller's transaction.

The caller commits, and afterwards updates the survivor's dossier field in the
index when step 2 gave it a membership (`moved`).
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import dossiers
from .models import Document, DossierDocument
from .pipeline import transition
from .states import State


class SupersessionError(ValueError):
    pass


def supersede(session: Session, copy_id: UUID, survivor_id: UUID, *, actor: str,
              batch: str | None = None, index=None,
              as_object: str | None = None) -> dict:
    """Retire `copy_id` in favour of `survivor_id`. Idempotent per pair.

    `as_object`: the copy is a copy of that object rather than of its own key.
    OCR recovery is the one case: a scan whose OCR'd PDF turns out to be an
    object another document already holds. The copy keeps its own key -- the
    scan is what it is -- and the record says which object made it a copy.
    """
    copy = session.get(Document, copy_id)
    survivor = session.get(Document, survivor_id)
    if copy is None or survivor is None:
        raise SupersessionError("both documents have to exist")
    if copy.id == survivor.id:
        raise SupersessionError("a document cannot supersede itself")
    if (as_object or copy.object_key) != survivor.object_key:
        raise SupersessionError("not a copy: the object keys differ")
    if survivor.superseded_by is not None:
        raise SupersessionError("the survivor is itself superseded")
    if copy.superseded_by is not None:
        if copy.superseded_by == survivor.id:
            return {"superseded": False, "moved": 0, "removed": 0, "index_entry": False}
        raise SupersessionError("already superseded by another document")

    index_entry = bool(index.delete(str(copy.id))) if index is not None else False

    reason = f"superseded by {survivor.id}"
    moved = removed = 0
    for dossier_id in session.execute(
            select(DossierDocument.dossier_id)
            .where(DossierDocument.document_id == copy.id)).scalars().all():
        moved += dossiers.add(session, dossier_id, survivor.id, actor=actor, batch=batch)
        removed += dossiers.remove(session, dossier_id, copy.id, actor=actor,
                                   reason=reason, batch=batch)

    payload = {"superseded_by": str(survivor.id), "actor": actor, "batch": batch}
    if as_object:
        payload["as_object"] = as_object
    transition(session, copy.id, State.SUPERSEDED, step="supersede", payload=payload)
    copy.superseded_by = survivor.id
    session.flush()
    return {"superseded": True, "moved": moved, "removed": removed,
            "index_entry": index_entry}
