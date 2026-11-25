# SPDX-License-Identifier: MIT
"""The one decision both reveal routes make, in the order that keeps the
last existence oracle from leaking (reveal-authorize-first, closes #487).

Before this module, each route resolved its grant, THEN looked up the
document (state, supersession, domain, box map) before asking whether the
grant actually covered it -- so a 404 "unknown grant" vs. "unknown document",
a 409 naming a survivor, or a 410 told any caller holding any grant id which
documents exist, which are deleted, and which copy a superseded one points to.

``decide()`` judges the grant first and answers every caller it does not
cover with the same ``REFUSAL`` -- no 404, no 409, no 410, and no document
read at all for a grant that fails without one.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .audit import current_state
from .grants import Grant, authorize, permitted_types
from .keys import DEFAULT_DOMAIN
from .models import BoxMap, Document
from .pipeline import document_domain, get_anonymized_text
from .states import State
from .vc import VcError, apply_vc_gate

#: Every refusal to a caller a grant does not cover, whatever the cause --
#: unknown grant, revoked, expired, wrong document, wrong recipient, unknown
#: document, superseded, deleted, or out of scope. One constant, raised fresh
#: each time (an ``HTTPException`` carries no state worth sharing).
REFUSAL = {"status_code": 403, "detail": "grant not applicable"}


@dataclass
class Decision:
    """What a route needs to finish a reveal, once the grant covers it."""

    grant: Grant
    permitted: set[str]
    domain: str
    vc_types: set[str]
    vc_audit: dict
    pseudo_text: str
    box_map: BoxMap | None


def decide(
    session: Session,
    grant_store,
    grant_id: str,
    document_id: UUID,
    *,
    caller: str | None,
    auth_enabled: bool,
    allow_global: bool,
    now: datetime,
    pdf: bool,
    resolve_role: Callable[[str], set[str]] | None,
    global_roles: Iterable[str],
    vc_public_key,
    vc_expected_vct: str | None,
    vc_expected_issuer: str | None,
    vc_required: bool,
    x_vc: str | None,
) -> Decision:
    """Refuse, or return what the route needs to answer.

    Two ``authorize()`` calls, not one: the first judges the grant on ITS OWN
    domain, before any row about ``document_id`` is read -- status, recipient,
    expiry, scope and the global-grant gate all run here, so a grant that
    fails on any of them never costs a document read. The second repeats the
    same check with the DOCUMENT's domain, once the document is known to
    exist. Dropping the second loses the domain binding (a scoped-elsewhere
    or unscoped-elsewhere grant would then reach the document); dropping the
    first brings the existence oracle back (every grant id would cost a
    document read, and an unknown grant would need its own answer). Both are
    needed and neither may move.
    """
    grant = grant_store.get(grant_id)
    if grant is None:
        raise HTTPException(**REFUSAL)
    permitted = permitted_types(grant, resolve_role)
    if not authorize(grant, document_id, permitted, now,
                     grant.domain or DEFAULT_DOMAIN, allow_global, caller,
                     auth_enabled, resolve_role=resolve_role,
                     global_roles=global_roles):
        raise HTTPException(**REFUSAL)

    # Only now: the document. Both reads always run, so an unknown id costs
    # exactly what a document in another domain costs -- neither answers
    # faster than the other.
    state = current_state(session, document_id)
    dom = document_domain(session, document_id)
    if state is None:
        raise HTTPException(**REFUSAL)  # a grant covers no document that does not exist
    covered = authorize(grant, document_id, permitted, now, dom, allow_global,
                        caller, auth_enabled, resolve_role=resolve_role,
                        global_roles=global_roles)
    if not covered:
        raise HTTPException(**REFUSAL)

    # The VC gate is pure (no reads) and part of "covered": a caller it
    # rejects hears nothing about deletion or supersession either.
    try:
        vc_types, vc_audit = apply_vc_gate(
            covered, x_vc, public_key=vc_public_key,
            expected_vct=vc_expected_vct, expected_issuer=vc_expected_issuer,
            required=vc_required, now=now,
        )
    except VcError as exc:
        raise HTTPException(status_code=403, detail=f"vc rejected: {exc}")

    # Covered: now the answers that only a covered caller hears.
    if state == State.DELETED:
        raise HTTPException(status_code=410, detail="document deleted")
    copy = session.get(Document, document_id)
    if copy is not None and copy.superseded_by is not None:
        raise HTTPException(
            status_code=409,
            detail=f"document is superseded by {copy.superseded_by}; "
                   "reveal on that one")
    box_map = None
    if pdf:
        box_map = session.get(BoxMap, document_id)
        if box_map is None:
            raise HTTPException(
                status_code=409,
                detail="no box map yet (reversible mode required; "
                       "reanonymize to build one)")
    pseudo_text = get_anonymized_text(session, document_id)
    if pseudo_text is None:
        raise HTTPException(status_code=409, detail="document not yet de-identified")

    return Decision(grant=grant, permitted=permitted, domain=dom,
                    vc_types=vc_types, vc_audit=vc_audit,
                    pseudo_text=pseudo_text, box_map=box_map)
