# SPDX-License-Identifier: MIT
"""Whether a document is gone for a route that answers its content
(deleted-document-answers-410, design.md decision 4).

Absence of text, a box map or the stored object has more than one cause --
that is what produced "not yet de-identified" for a document whose content a
deletion removed. Whether a document is deleted is decided from its state,
derived from the audit chain, and from nothing else.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .audit import current_state
from .states import State


def check(session: Session, document_id: UUID) -> State:
    """Raise 404 ``unknown document`` when the document has no state, 410
    ``document deleted`` when its state is `State.DELETED`. Returns the state
    otherwise, so the caller does not read it twice."""
    state = current_state(session, document_id)
    if state is None:
        raise HTTPException(status_code=404, detail="unknown document")
    if state == State.DELETED:
        raise HTTPException(status_code=410, detail="document deleted")
    return state
