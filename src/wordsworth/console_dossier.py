# SPDX-License-Identifier: MIT
"""The console starts on a dossier (console-dossier-home).

A key user starts from a dossier, not from a list of the 200 documents the
straat touched last — on the live installation those were all deleted ones.
Searching already refuses to run without a dossier and topics are per dossier,
so the home page asks that question first: which dossier. With exactly one,
there is nothing to decide and the console opens on it.

The dossier is addressed by query parameter, ``/console/dossier?dossier=<name>``,
like every other console page. Names are free text: a name with a slash would
match no route as a path segment, and then the 404 that lists the dossiers could
never be reached for it.

The page adds no ranking and no filter of its own. The question box posts to
`/console/search`, a topic links to search within that topic, and the documents
come from the same query as the full list (`console_list.documents`), so the
rule that hides deleted and superseded documents is the one rule of
console-hide-deleted and not a second copy here.
"""
from __future__ import annotations

from urllib.parse import quote

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from . import console_data, console_list, dossiers
from . import topics as topics_mod
from .topic_claim import claim
from .models import Document, Dossier, DossierDocument, Topic


def page_url(name: str) -> str:
    """The dossier page's address. Everything in the name is encoded, slash
    included, so the name comes back exactly as it was written."""
    return f"/console/dossier?dossier={quote(name, safe='')}"


def choices(session) -> list[dict]:
    """Every dossier with its number of LIVE documents and of topics.

    Not `dossiers.listing`: that counts every member, deleted ones included, and
    a picker that says 415 where 2 can be opened misleads the one reading it.
    Live is counted in one query with the console's one hiding rule.
    """
    states = console_data.latest_state_subquery()
    hidden = console_data.hidden_condition(states.c.to_state,
                                           Document.superseded_by)
    live = (select(DossierDocument.dossier_id.label("dossier_id"),
                   func.count(Document.id).label("n"))
            .join(Document, Document.id == DossierDocument.document_id)
            .outerjoin(states, states.c.document_id == Document.id)
            .where(~hidden)
            .group_by(DossierDocument.dossier_id).subquery())
    topics = (select(Topic.dossier_id.label("dossier_id"),
                     func.count(Topic.id).label("n"))
              .group_by(Topic.dossier_id).subquery())
    rows = session.execute(
        select(Dossier.name, func.coalesce(live.c.n, 0),
               func.coalesce(topics.c.n, 0))
        .outerjoin(live, live.c.dossier_id == Dossier.id)
        .outerjoin(topics, topics.c.dossier_id == Dossier.id)
        .order_by(Dossier.created_at.desc()))
    return [{"name": name, "live": n_live, "topics": n_topics,
             "href": page_url(name)} for name, n_live, n_topics in rows]


def topic_rows(dossier: Dossier, listed: list[Topic]) -> list[dict]:
    """The dossier's topics as `topics.listing` gives them (largest first),
    each with a link that searches within it."""
    base = f"/console/search?dossier={quote(dossier.name, safe='')}"
    return [{"name": topics_mod.display_name(t), "count": t.document_count,
             "claim": claim(t), "href": f"{base}&topic={t.id}"} for t in listed]


def coverage(topics: list[dict], live: int) -> dict:
    """"x van y documenten vallen in een onderwerp".

    A topic list that covers under half the dossier reads as the whole dossier
    unless the page says how much it covers. ``x`` is the sum of the topics'
    counts as they were computed; ``y`` is the live count now. When documents
    were deleted since the computation, ``x`` can exceed ``y``; then the page
    says the topics are stale instead of a fraction above one, and the number
    is not clamped (a clamped 3 van 3 would claim a coverage nobody measured).
    """
    in_topic = sum(t["count"] for t in topics)
    return {"in_topic": in_topic, "live": live, "stale": in_topic > live}


def mount(router, session_factory, TEMPLATES, mag_lezen, caller) -> None:
    def _picker(request, found, status_code=200, fout=""):
        return TEMPLATES.TemplateResponse(request, "dossiers.html", {
            "dossiers": found, "fout": fout, "caller": caller(request)},
            status_code=status_code)

    @router.get("", response_class=HTMLResponse, include_in_schema=False)
    def home(request: Request):
        """The dossier picker; with exactly one dossier, that dossier."""
        mag_lezen(request)
        with session_factory() as session:
            found = choices(session)
        if len(found) == 1:
            return RedirectResponse(found[0]["href"], status_code=303)
        return _picker(request, found)

    @router.get("/dossier", response_class=HTMLResponse,
                include_in_schema=False)
    def dossier_page(request: Request, dossier: str = "", alles: bool = False):
        mag_lezen(request)
        if not dossier:
            # No name is not an unknown name: the question "which dossier" is
            # asked on one page, and that is where this goes.
            return RedirectResponse("/console", status_code=303)
        with session_factory() as session:
            found = dossiers.named(session, dossier)
            if found is None:
                # Named, not empty: an empty page for a typo reads as "this
                # dossier holds nothing", which is a different answer.
                return _picker(request, choices(session), 404,
                               f"Dossier “{dossier}” bestaat niet.")
            listed = topics_mod.listing(session, found.id)
            topics = topic_rows(found, listed)
            docs = console_list.documents(session, alles, found.id)
            # Every topic of one computation carries the same moment.
            computed_at = (listed[0].computed_at.strftime("%Y-%m-%d %H:%M")
                           if listed else "")
        here = page_url(found.name)
        return TEMPLATES.TemplateResponse(request, "dossier.html", {
            **docs, **console_list.toggle(here), "alles": alles,
            "dossier": found.name, "topics": topics,
            "topics_url": f"/console/topics?dossier={quote(found.name, safe='')}",
            "coverage": coverage(topics, docs["live"]),
            "computed_at": computed_at, "caller": caller(request)})
