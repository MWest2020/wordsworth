# SPDX-License-Identifier: MIT
"""What a dossier change leaves behind, and where.

A dossier decides what a scoped search returns, so moving a document changes
what someone does and does not see. Until now nothing recorded that: the
security review grepped for `audit` across `dossiers.py`, `dossier_tools.py`
and `backfill_dossier.py` and found **nothing**. Afterwards you could see the
outcome and not the act — while the question anyone asks a month later is
exactly "who moved this, and when".

Two kinds of fact, two homes, and the split is the whole point:

**A membership is about one document.** Adding or removing one belongs on that
document's own hash chain, as an *event* (from == to), the way `deanonymize`
is an event: the document does not change state by landing in another case.

**A rename is about the dossier.** It moves no document and changes no
membership; it changes a label that a thousand documents happen to share.
Writing a thousand identical records would fill the chain with copies of one
fact, and a single record without a document does not fit that table at all.
So it goes where the other document-less authorisation facts already live: the
key-lifecycle stream, beside grants, key rotations and role changes. The same
reasoning is written out in `roles.py`.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import audit
from .models import Dossier, DossierDocument
from .pipeline import current_state

#: Steps, kept apart so a reader of the trail can filter on the act rather than
#: having to interpret a payload.
ADDED = "dossier_added"
REMOVED = "dossier_removed"


class MissingAuditStream(RuntimeError):
    """A write that must be recorded was given nowhere to record it."""


def name_of(session: Session, dossier_id: UUID) -> str:
    """The dossier's name, for the trail. Read BEFORE a delete: afterwards the
    row may be gone, and a record that cannot name the dossier is half a record.
    Falls back to the id rather than to nothing."""
    found = session.get(Dossier, dossier_id)
    return found.name if found is not None else str(dossier_id)


def membership_changed(session: Session, *, document_id: UUID, dossier_id: UUID,
                       dossier: str, step: str, actor: str,
                       reason: str | None = None, batch: str | None = None) -> None:
    """Record that this document entered or left a dossier.

    `from == to`: an event, not a state transition. A document that moves from
    one case to another is in exactly the state it was before; claiming a
    transition would make `current_state` lie.

    `batch` ties the records of ONE human action together. A backfill that
    assigns 791 documents is honest as 791 records — every document really did
    get a membership — and unreadable without something that says they were one
    act. With it, a reader can collapse them; without it, a day of history looks
    like 791 unrelated decisions.
    """
    state = current_state(session, document_id)
    if state is None:
        # No chain to append to. Registration writes the first record, so this
        # means the document does not exist yet — a caller error, not something
        # to paper over with a phantom state.
        raise ValueError(f"document {document_id} has no audit record to extend")
    payload: dict = {"dossier": dossier, "dossier_id": str(dossier_id), "actor": actor}
    if reason:
        payload["reason"] = reason
    if batch:
        payload["batch"] = batch
    audit.append(session, document_id=document_id, from_state=state.value,
                 to_state=state.value, step=step, payload=payload)


def renamed(session: Session, lifecycle, *, dossier, old: str, actor: str) -> None:
    """Record a rename in the key-lifecycle stream.

    Counts the members here rather than at the call site, because that number is
    the reason this record exists: it says how far one rename reached, without
    writing the same fact once per document.

    No stream is an error. This used to return quietly on `lifecycle=None`,
    with a docstring promising that "a caller from the API always passes one".
    There was no API rename path; the only caller -- the CLI -- passed nothing,
    so no rename was ever recorded and the sentence made that look deliberate
    (found 2026-09-23, key-audit-in-postgres). A missing record should be an
    error someone sees, not a default someone chose.
    """
    if lifecycle is None:
        raise MissingAuditStream("a dossier rename needs the key-lifecycle stream")
    documents = session.execute(
        select(func.count()).select_from(DossierDocument)
        .where(DossierDocument.dossier_id == dossier.id)).scalar_one()
    lifecycle.dossier_renamed(dossier_id=str(dossier.id), old=old,
                              new=dossier.name, documents=int(documents),
                              actor=actor)
