# SPDX-License-Identifier: MIT
"""A screen for reading what the pipeline produced (document-console).

The straat is followable today through an endpoint, an audit record and a
Prometheus counter. That serves whoever knows the API and is useless for the
conversation this project is about: put a document in front of someone, put the
pseudonymised version next to it, and ask whether it is right.

Two rules hold this module together.

It shows the ARTEFACT. The stored pseudonymised text, with its tokens marked —
not a re-run of the detectors over the source. A re-run answers "what would the
detectors say today", which is a different question from "what did the pipeline
do", and confusing the two is how you end up reporting on your instrument.

It never reveals. Re-identification has exactly one door: the grant-gated,
audited reveal. An inspection screen that may also reveal is a second door with
a friendlier name, and it is the one nobody audits.
"""
from __future__ import annotations

import re
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from . import combinations as _combinations
from .auth import CONSOLE_COOKIE
from .models import (AuditRecord, DeclaredCombination, Document,
                     DocumentPseudonym, DocumentText)
from .pipeline import current_state

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_TOKEN = re.compile(r"\[([A-Z0-9_]+):([0-9a-f]{8})\]")


def marked(text: str) -> list[dict]:
    """Split pseudonymised text into plain runs and typed tokens.

    Done here rather than in the template so the page never has to decide what
    is a token; the regex is the same shape the registry uses.
    """
    parts, at = [], 0
    for m in _TOKEN.finditer(text or ""):
        if m.start() > at:
            parts.append({"text": text[at:m.start()], "type": None})
        parts.append({"text": m.group(0), "type": m.group(1)})
        at = m.end()
    if at < len(text or ""):
        parts.append({"text": text[at:], "type": None})
    return parts


def types_per_document(session) -> dict:
    """``document_id -> {LABEL: count}`` from the registered pseudonyms."""
    rows = session.execute(select(DocumentPseudonym.document_id,
                                  DocumentPseudonym.pseudonym))
    out: dict = {}
    for doc_id, token in rows:
        label = token[1:].split(":")[0].upper()
        out.setdefault(doc_id, {})
        out[doc_id][label] = out[doc_id].get(label, 0) + 1
    return out


def reach(session, types: set[str]) -> tuple[int, list[str]]:
    """How many documents carry EVERY one of these types, and which of them the
    corpus cannot show at all.

    A type no detector emits occurs nowhere, and a bare 0 then reads as "does
    not occur" when the true answer is "cannot be seen". The screen has to say
    which, or the number quietly reassures.
    """
    wanted = {t.upper() for t in types}
    per_doc = types_per_document(session)
    seen = {lbl for present in per_doc.values() for lbl in present}
    return (sum(1 for present in per_doc.values() if wanted <= set(present)),
            sorted(wanted - seen))


def build_router(session_factory) -> APIRouter:
    router = APIRouter(prefix="/console", tags=["console"])

    def _caller(request: Request) -> str:
        return request.scope.get("state", {}).get("caller", "onbekend")

    @router.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login_form(request: Request, fout: str = ""):
        return TEMPLATES.TemplateResponse(request, "login.html", {"fout": fout})

    @router.post("/login", include_in_schema=False)
    def login(key: str = Form(...)):
        # The cookie holds the key itself, so it is exactly as strong as the
        # header: same key set, same label. HttpOnly keeps it away from script,
        # SameSite=strict keeps it off cross-site requests.
        r = RedirectResponse("/console", status_code=303)
        r.set_cookie(CONSOLE_COOKIE, key, httponly=True, samesite="strict",
                     max_age=8 * 3600)
        return r

    @router.get("", response_class=HTMLResponse, include_in_schema=False)
    def index(request: Request):
        with session_factory() as session:
            per_doc = types_per_document(session)
            # Most recently touched first. `documents` has no timestamp — the
            # audit trail is where time lives in this system — so the ordering
            # comes from the latest audit record, which is also the more useful
            # answer: "what did the straat do last".
            latest = (select(AuditRecord.document_id,
                             func.max(AuditRecord.seq).label("seq"))
                      .group_by(AuditRecord.document_id).subquery())
            docs = []
            for d in session.execute(
                    select(Document).outerjoin(latest,
                                               latest.c.document_id == Document.id)
                    .order_by(latest.c.seq.desc().nullslast()).limit(200)).scalars():
                state = current_state(session, d.id)
                docs.append({"id": str(d.id), "key": d.object_key,
                             "state": state.value if state else "—",
                             "types": sorted(per_doc.get(d.id, {}).items())})
            total = session.execute(select(func.count(Document.id))).scalar_one()
        return TEMPLATES.TemplateResponse(request, "index.html", {
            "docs": docs, "total": total, "caller": _caller(request)})

    @router.get("/documents/{document_id}", response_class=HTMLResponse,
                include_in_schema=False)
    def document(request: Request, document_id: UUID):
        with session_factory() as session:
            row = session.get(DocumentText, document_id)
            doc = session.get(Document, document_id)
            state = current_state(session, document_id) if doc else None
            counts = types_per_document(session).get(document_id, {})
            declared = _declared(session)
            present = {t.upper() for t in counts}
            unbroken = [d for d in declared
                        if not ({t.upper() for t in d["types"]} & present)]
            carried = [d for d in declared
                       if {t.upper() for t in d["types"]} <= present]
        return TEMPLATES.TemplateResponse(request, "document.html", {
            "id": str(document_id), "key": doc.object_key if doc else None,
            "state": state.value if state else "—",
            "parts": marked(row.anonymized_text if row else ""),
            "missing": row is None, "counts": sorted(counts.items()),
            "unbroken": unbroken, "carried": carried})

    @router.get("/combinations", response_class=HTMLResponse,
                include_in_schema=False)
    def combinations_page(request: Request, fout: str = ""):
        with session_factory() as session:
            rows = _declared(session, session)
        return TEMPLATES.TemplateResponse(request, "combinations.html",
                                          {"rows": rows, "fout": fout})

    @router.post("/combinations", include_in_schema=False)
    def declare(request: Request, types: str = Form(...), reason: str = Form("")):
        wanted = sorted({t.strip().upper() for t in re.split(r"[,\s]+", types)
                         if t.strip()})
        try:
            _combinations.parse([{"types": wanted, "reason": reason}])
        except _combinations.CombinationError as exc:
            return RedirectResponse(f"/console/combinations?fout={exc}",
                                    status_code=303)
        with session_factory() as session:
            session.merge(DeclaredCombination(
                types="+".join(wanted), reason=reason.strip(),
                declared_by=_caller(request)))
            session.commit()
        return RedirectResponse("/console/combinations", status_code=303)

    def _declared(session, with_reach=None) -> list[dict]:
        out = []
        for row in session.execute(select(DeclaredCombination).order_by(
                DeclaredCombination.created_at)).scalars():
            types = row.types.split("+")
            item = {"types": types, "reason": row.reason, "by": row.declared_by}
            if with_reach is not None:
                item["documents"], item["unobservable"] = reach(with_reach,
                                                                set(types))
            out.append(item)
        return out

    return router
