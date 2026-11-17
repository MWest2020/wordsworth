"""The one gate both reveal routes call (#487, `reveal-authorize-first`).

Before this module, `reveal` and `reveal.pdf` answered about the document --
its existence, its supersession, its deletion -- before the grant had decided
anything. Anyone holding a key and any grant id, not their own, could tell
which document ids exist (404 vs 403), which are deleted (410), and the id of
the live copy a superseded one points to.

`decide()` judges the grant FIRST, on the grant's own domain, so a grant that
fails there is refused without a single read of the document: its state, its
row, whether it is superseded, its domain, its box map, its text or its
pseudonyms. Only a grant that is covered -- active, matching recipient (when
caller auth is on), unexpired, in scope, and (for an unscoped grant) allowed to
be global -- earns a second look, this time at the document's real domain.
Every refusal before or at that point is the same answer: `REFUSAL`. Only a
caller the grant covers past both checks, and the credential gate where
configured, learns whether the document is deleted or superseded.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .audit import current_state
from .grants import Grant, GrantStore, authorize, permitted_types
from .keys import DEFAULT_DOMAIN
from .models import BoxMap, Document
from .pipeline import document_domain, get_anonymized_text
from .states import State
from .vc import VcError, apply_vc_gate

REFUSAL = HTTPException(status_code=403, detail="grant not applicable")


@dataclass
class Decision:
    """What a route needs once the caller is covered -- nothing more."""

    grant: Grant
    domain: str
    permitted: set[str]
    vc_allowed: set[str]
    vc_audit: dict
    pseudo_text: str
    box_map: BoxMap | None


def decide(
    session: Session,
    grant_store: GrantStore,
    grant_id: str,
    document_id: UUID,
    *,
    caller: str | None,
    auth_enabled: bool,
    allow_global: bool,
    now: datetime,
    pdf: bool,
    resolve_role: Callable[[str], set[str]],
    global_roles: Iterable[str],
    x_vc: str | None,
    vc_public_key,
    vc_expected_vct: str | None = None,
    vc_expected_issuer: str | None = None,
    vc_required: bool = False,
) -> Decision:
    """Judge the grant, then the document, raising the uniform refusal (or a
    410/409/403-vc-rejected for a covered caller) the moment either fails.

    `authorize()` is called twice, deliberately, not as a shortcut for one
    call: the first time with the grant's OWN domain, so the domain
    comparison holds trivially and every other check (status, recipient,
    expiry, scope, the global-grant gate, role resolution) runs before any
    document read; the second time with the document's REAL domain, which
    only a read can supply. Dropping the second call loses the domain
    binding; dropping the first brings the existence oracle back -- an
    unscoped grant from the wrong domain would otherwise read the document
    before being refused.
    """
    grant = grant_store.get(grant_id)
    if grant is None:
        raise REFUSAL
    permitted = permitted_types(grant, resolve_role)
    if not authorize(grant, document_id, permitted, now,
                     grant.domain or DEFAULT_DOMAIN, allow_global, caller,
                     auth_enabled, resolve_role=resolve_role,
                     global_roles=global_roles):
        raise REFUSAL

    # Both reads always run -- an unknown id costs what a document in another
    # domain costs, so neither leaks through a cheaper code path.
    state = current_state(session, document_id)
    dom = document_domain(session, document_id)
    if state is None:
        raise REFUSAL
    allowed = authorize(grant, document_id, permitted, now, dom, allow_global,
                        caller, auth_enabled, resolve_role=resolve_role,
                        global_roles=global_roles)
    if not allowed:
        raise REFUSAL

    # The VC gate is pure and reads nothing, so it costs nothing to decide
    # here, before any answer about deletion or supersession.
    try:
        vc_allowed, vc_audit = apply_vc_gate(
            allowed, x_vc, public_key=vc_public_key,
            expected_vct=vc_expected_vct, expected_issuer=vc_expected_issuer,
            required=vc_required, now=now)
    except VcError as exc:
        raise HTTPException(status_code=403, detail=f"vc rejected: {exc}") from exc

    # Covered: only now do deletion, supersession and readiness get an answer.
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

    return Decision(grant=grant, domain=dom, permitted=permitted,
                    vc_allowed=vc_allowed, vc_audit=vc_audit,
                    pseudo_text=pseudo_text, box_map=box_map)
