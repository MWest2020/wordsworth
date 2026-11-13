# SPDX-License-Identifier: MIT
"""The document list, "alle documenten" (console-dossier-home).

This was the console's home page until the console started on a dossier. It
moved here unchanged in behaviour, to ``/console/documents``, because an
operator still needs the whole corpus in one place; a key user starts from a
dossier instead.

The query is shared with the dossier page, which shows the same rows for one
dossier. One query for both means one meaning of "hidden" and one meaning of
"most recently touched", not two that drift apart.
"""
from __future__ import annotations

from uuid import UUID

from fastapi import Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from . import console_data
from .console_data import label, types_per_document
from .models import AuditRecord, Document, DossierDocument
from .states import State

#: As many rows as a page shows. The total next to it says how many there are.
CAP = 200


def documents(session, alles: bool, dossier_id: UUID | None = None) -> dict:
    """The rows of the list, newest first, and the counts that go with them.

    ``alles`` is the explicit toggle: a deleted or superseded document is hidden
    unless the reader asks for it (console-hide-deleted). ``dossier_id`` narrows
    to one dossier's members. ``live`` is the number of documents not hidden,
    whatever the toggle says; ``total`` is what the rows below it are counted
    from.
    """
    per_doc = types_per_document(session)
    # Most recently touched first. `documents` has no timestamp — the audit
    # trail is where time lives in this system — so the ordering comes from the
    # latest audit record, which is also the more useful answer: "what did the
    # straat do last".
    latest = (select(AuditRecord.document_id,
                     func.max(AuditRecord.seq).label("seq"))
              .group_by(AuditRecord.document_id).subquery())
    states = console_data.latest_state_subquery()
    hidden = console_data.hidden_condition(states.c.to_state,
                                           Document.superseded_by)
    rows = (select(Document, states.c.to_state)
            .outerjoin(latest, latest.c.document_id == Document.id)
            .outerjoin(states, states.c.document_id == Document.id)
            .order_by(latest.c.seq.desc().nullslast()))
    counted = (select(func.count(Document.id))
               .outerjoin(states, states.c.document_id == Document.id))
    if dossier_id is not None:
        members = Document.id.in_(
            select(DossierDocument.document_id)
            .where(DossierDocument.dossier_id == dossier_id))
        rows, counted = rows.where(members), counted.where(members)
    if not alles:
        rows = rows.where(~hidden)
    docs = []
    for d, to_state in session.execute(rows.limit(CAP)):
        state = State(to_state) if to_state else None
        docs.append({"id": str(d.id), "key": label(d),
                     "state": state.value if state else "—",
                     "types": sorted(per_doc.get(d.id, {}).items())})
    live = session.execute(counted.where(~hidden)).scalar_one()
    return {
        "docs": docs, "live": live,
        "total": session.execute(counted).scalar_one() if alles else live,
        # How many are hidden right now, shown regardless of the toggle so the
        # notice (and its "show them" / "hide them again" link) match what the
        # corpus actually holds.
        "hidden_total": session.execute(counted.where(hidden)).scalar_one(),
    }


def toggle(base: str) -> dict:
    """The two links of the hidden-documents notice, for a page at ``base``."""
    join = "&" if "?" in base else "?"
    return {"show_url": f"{base}{join}alles=1", "hide_url": base}


def mount(router, session_factory, TEMPLATES, mag_lezen, caller) -> None:
    @router.get("/documents", response_class=HTMLResponse,
                include_in_schema=False)
    def index(request: Request, alles: bool = False):
        mag_lezen(request)
        with session_factory() as session:
            found = documents(session, alles)
        return TEMPLATES.TemplateResponse(request, "index.html", {
            **found, **toggle("/console/documents"), "alles": alles,
            "caller": caller(request)})
