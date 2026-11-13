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

from uuid import UUID

from fastapi import BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse

from . import concurrency
from . import topics as topics_mod
from .console_topic_label import BEZIG, LABEL_SLOT, LOOPT_AL, in_background
from .dossiers import DossierError
from .search_index import SearchUnavailable
from .models import Dossier, Topic


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
         "document_count": t.document_count, "computed_at": t.computed_at,
         "llm_label": t.llm_label, "llm_description": t.llm_description,
         "llm_model": t.llm_model,
         "llm_at": t.llm_at.strftime("%Y-%m-%d") if t.llm_at else ""}
        for t in topics_mod.listing(session, dossier_id)
    ]


def mount(router, session_factory, search_index, TEMPLATES, mag_lezen=None,
          caller=None, generator=None) -> None:
    def _page(request, dossier: str, fout: str = "", uitkomst=None,
              melding: str = ""):
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
            "uitkomst": uitkomst, "q": "", "melding": melding,
            "kan_labelen": generator is not None and search_index is not None,
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
            try:
                uitkomst = topics_mod.compute(session, search_index, gevonden.id)
            except SearchUnavailable:
                # Berekenen leest het hele dossier uit de index; zonder index
                # kan dat niet. De REEDS berekende onderwerpen staan in de
                # database en blijven op deze pagina staan -- dat is het
                # verschil dat hier verteld moet worden.
                return _page(request, dossier,
                             "Onderwerpen berekenen kan nu niet: de zoekindex "
                             "is onbereikbaar. Wat eerder berekend is, staat er "
                             "nog en blijft bruikbaar.")
            session.commit()
        return _page(request, dossier, uitkomst={
            "seen": uitkomst.seen, "with_vector": uitkomst.with_vector,
            "without_topic": uitkomst.without_topic,
            "distance": uitkomst.distance, "min_size": uitkomst.min_size,
            "max_share": uitkomst.max_share})

    @router.post("/topics/{topic_id}/label", include_in_schema=False)
    def label_page(request: Request, topic_id: UUID, achtergrond: BackgroundTasks,
                   dossier: str = Form(...)):
        """Start een label en wacht er niet op (topic-labels-llm).

        Een label is twee minuten modeltijd, en een browser gaat door
        Cloudflare (100 s) en oauth2-proxy (30 s): een knop die wacht, krijgt
        een foutmelding voor werk dat daarna wél lukt. Dus komt de pagina
        meteen terug, en schrijft de server het label in een achtergrondtaak
        van dit verzoek. Eén tegelijk; een tweede klik start niets.
        """
        if mag_lezen is not None:
            mag_lezen(request)
        if search_index is None or generator is None:
            return _page(request, dossier, "Deze instantie draait zonder "
                         "zoekindex of taalmodel; een label schrijven kan hier niet.")
        with session_factory() as session:
            if session.get(Topic, topic_id) is None:
                return _page(request, dossier, "Dat onderwerp bestaat niet "
                             "(meer); misschien is het dossier herberekend.")
        slot = concurrency.limiter(LABEL_SLOT, 1)
        if not slot.acquire(blocking=False):
            return _page(request, dossier, melding=LOOPT_AL)
        # Vanaf hier is het slot van dit verzoek. Alleen de achtergrondtaak geeft
        # het vrij; komt het daar niet, dan zat de knop vast tot een herstart.
        try:
            pagina = _page(request, dossier, melding=BEZIG)
            achtergrond.add_task(in_background, session_factory, search_index,
                                 generator, topic_id, slot)
        except BaseException:
            slot.release()
            raise
        return pagina
