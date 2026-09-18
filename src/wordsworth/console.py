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

It has no way out of its own. Revealing happens through the existing grant-gated,
audited endpoint, called from the page with the viewer's own cookie — no
authorisation logic here, no keys here, no audit of its own. The rule that
matters is not "the console must not reveal" but "the console must not have a
second door"; a person using the same audited door with a screen instead of
``curl`` walks through the first one.

A refusal is therefore shown, not hidden. A department that does not hold the key
does not get it from a prettier page either, and watching that happen is the
demonstration.
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
from . import console_data
from . import console_search
from . import console_topics
from .auth import CONSOLE_COOKIE
from .console_data import label, marked, reach, types_per_document
from .models import AuditRecord, DeclaredCombination, Document, DocumentText
from .pipeline import current_state

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
#: Self-hosted fonts and stylesheet. A sovereignty demo that fetches its letters
#: from Google refutes itself in the network inspector, and this screen exists to
#: be looked at closely. Mounted on the app (see api.py) because a Mount added to
#: an APIRouter does not pick up the router's prefix.
STATIC_DIR = Path(__file__).parent / "static"


def build_router(session_factory, keys: dict[str, str],
                 search_index=None, guard=None) -> APIRouter:
    router = APIRouter(prefix="/console", tags=["console"])

    def _caller(request: Request) -> str:
        return request.scope.get("state", {}).get("caller", "onbekend")

    def _mag_lezen(request: Request) -> None:
        """Dezelfde poort als /documents/{id}/anonymized en /export.

        Zonder dit toont de console dezelfde gepseudonimiseerde tekst aan een
        beller die op die endpoints een 403 krijgt — en dan is de console de
        tweede deur die de docstring hierboven verbiedt.
        """
        if guard is not None:
            guard(request)

    @router.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login_form(request: Request, fout: str = ""):
        """The key form, always reachable.

        Someone who already has an identity never arrives here: they open
        /console and the middleware knows them, so there is nothing to skip. And
        this page is exempt from authentication — it cannot know who you are
        anyway, which is why an earlier attempt to skip it never fired.

        Reachable ON PURPOSE. Behind an identity provider the assertion rides
        along on every request, so without a door to the key route a person
        behind that provider could never choose anything else. Logging in here
        sets the cookie, and a presented credential wins; /console/logout hands
        the identity back.
        """
        return TEMPLATES.TemplateResponse(request, "login.html", {"fout": fout})

    @router.post("/login", include_in_schema=False)
    def login(request: Request, key: str = Form(...)):
        # Checked here, against the same key set the middleware uses, so that a
        # typo says so. Storing an unchecked key hands back a cookie that leads
        # to the same refusal — with the added confusion of having apparently
        # logged in. This decides whether to set a cookie; the middleware still
        # decides who gets in.
        if key not in keys:
            return TEMPLATES.TemplateResponse(
                request, "login.html",
                {"fout": "Die sleutel staat niet in de configuratie."},
                status_code=401)
        # The cookie holds the key itself, so it is exactly as strong as the
        # header: same key set, same label. HttpOnly keeps it away from script,
        # SameSite=strict keeps it off cross-site requests.
        r = RedirectResponse("/console", status_code=303)
        # Secure: de waarde ÍS de api-sleutel en Path=/ maakt hem geldig voor
        # elk endpoint. Zonder dit vlaggetje gaat hij mee over een http-verzoek
        # naar dezelfde host. Mijn docstring noemde HttpOnly en SameSite en sloeg
        # dit over.
        r.set_cookie(CONSOLE_COOKIE, key, httponly=True, samesite="strict",
                     secure=True, max_age=8 * 3600)
        return r

    @router.get("/logout", include_in_schema=False)
    def logout():
        """Without this, a stale cookie is a trap you escape only by digging
        through browser settings."""
        r = RedirectResponse("/console/login", status_code=303)
        r.delete_cookie(CONSOLE_COOKIE)
        return r

    @router.get("", response_class=HTMLResponse, include_in_schema=False)
    def index(request: Request):
        _mag_lezen(request)
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
                docs.append({"id": str(d.id), "key": label(d),
                             "state": state.value if state else "—",
                             "types": sorted(per_doc.get(d.id, {}).items())})
            total = session.execute(select(func.count(Document.id))).scalar_one()
        return TEMPLATES.TemplateResponse(request, "index.html", {
            "docs": docs, "total": total, "caller": _caller(request)})

    console_search.mount(router, session_factory, search_index, TEMPLATES,
                         _mag_lezen)
    console_topics.mount(router, session_factory, search_index, TEMPLATES,
                         _mag_lezen, _caller)

    @router.get("/documents/{document_id}", response_class=HTMLResponse,
                include_in_schema=False)
    def document(request: Request, document_id: UUID):
        _mag_lezen(request)
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
            grants, revoked = console_data.grants_for(session, document_id)
            history = console_data.reveal_history(session, document_id)
        return TEMPLATES.TemplateResponse(request, "document.html", {
            "id": str(document_id), "key": label(doc),
            "state": state.value if state else "—",
            "parts": marked(row.anonymized_text if row else ""),
            "missing": row is None, "counts": sorted(counts.items()),
            "unbroken": unbroken, "carried": carried,
            "grants": grants, "revoked": revoked, "history": history,
            "caller": _caller(request)})

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
            # Coderen: een reden met een & of een # erin brak anders de
            # querystring. Jinja escapet bij het renderen, dus dit is geen XSS
            # maar een boodschap die halverwege ophoudt.
            from urllib.parse import quote

            return RedirectResponse(
                f"/console/combinations?fout={quote(str(exc))}", status_code=303)
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
