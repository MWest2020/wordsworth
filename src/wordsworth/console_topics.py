# SPDX-License-Identifier: MIT
"""De onderwerpenpagina (onderwerpen).

Eén dossier tegelijk, met de onderwerpen die de laatste berekening opleverde en
— even belangrijk — wannéér dat was en over hoeveel documenten. Een lijst zonder
die twee leest als de huidige stand van het dossier, ook als hij vier maanden en
tweehonderd documenten oud is.

Doorklikken gaat naar zoeken binnen dat onderwerp, want dat is wat een onderwerp
ís: een versmalling van het zoeken, geen andere rangschikking.
"""
from __future__ import annotations

from fastapi import Form, Request
from fastapi.responses import HTMLResponse

from . import topics as topics_mod
from .dossiers import DossierError
from .models import Dossier


def _choices(session) -> list[dict]:
    from . import dossiers

    return [d for d in dossiers.listing(session) if d.get("name")]


def _named(session, naam: str) -> Dossier:
    from sqlalchemy import select

    found = session.execute(
        select(Dossier).where(Dossier.name == naam)).scalars().first()
    if found is None:
        raise DossierError(f"dossier {naam!r} bestaat niet")
    return found


def _rows(session, dossier_id) -> list[dict]:
    return [
        {"id": str(t.id), "name": topics_mod.display_name(t),
         "computed_name": t.computed_name, "given_name": t.given_name,
         "document_count": t.document_count, "computed_at": t.computed_at}
        for t in topics_mod.listing(session, dossier_id)
    ]


def mount(router, session_factory, search_index, TEMPLATES, mag_lezen=None,
          caller=None) -> None:
    def _page(request, dossier: str, fout: str = "", uitkomst=None):
        rows, berekend, gerekend_over = [], "", 0
        with session_factory() as session:
            keuzes = _choices(session)
            if dossier and not fout:
                try:
                    gevonden = _named(session, dossier)
                except DossierError as exc:
                    fout = str(exc)
                else:
                    rows = _rows(session, gevonden.id)
                    if rows:
                        # Alle onderwerpen van één berekening dragen hetzelfde
                        # moment; de eerste vertelt het dus voor alle.
                        berekend = rows[0]["computed_at"].strftime("%Y-%m-%d %H:%M")
                        gerekend_over = sum(r["document_count"] for r in rows)
        return TEMPLATES.TemplateResponse(request, "topics.html", {
            "dossier": dossier, "dossiers": keuzes, "topics": rows,
            "fout": fout, "berekend": berekend, "gerekend_over": gerekend_over,
            "uitkomst": uitkomst, "q": "",
            "caller": caller(request) if caller else ""})

    @router.get("/topics", response_class=HTMLResponse, include_in_schema=False)
    def topics_page(request: Request, dossier: str = "", fout: str = ""):
        if mag_lezen is not None:
            mag_lezen(request)
        return _page(request, dossier, fout)

    @router.post("/topics", include_in_schema=False)
    def compute_page(request: Request, dossier: str = Form(...)):
        """Herbereken en toon meteen het resultaat.

        Geen redirect-na-post hier: de noemer van de berekening (gezien, met
        vector, zonder onderwerp) bestaat alleen in dít antwoord, en die
        doorsluizen via de URL zou drie getallen tot queryparameters maken die
        iedereen kan verzinnen.
        """
        if mag_lezen is not None:
            mag_lezen(request)
        if search_index is None:
            return _page(request, dossier,
                         "Deze instantie draait zonder zoekindex.")
        with session_factory() as session:
            try:
                gevonden = _named(session, dossier)
            except DossierError as exc:
                return _page(request, dossier, str(exc))
            uitkomst = topics_mod.compute(session, search_index, gevonden.id)
            session.commit()
        return _page(request, dossier, uitkomst={
            "seen": uitkomst.seen, "with_vector": uitkomst.with_vector,
            "without_topic": uitkomst.without_topic,
            "distance": uitkomst.distance, "min_size": uitkomst.min_size})
