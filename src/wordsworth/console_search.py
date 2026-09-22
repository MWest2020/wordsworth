# SPDX-License-Identifier: MIT
"""The search page (dossier-scope).

Its own module because searching grew a world of its own -- a scope to resolve,
a picker to fill, and three different ways to have nothing to show that a reader
must be able to tell apart: no dossier chosen, a dossier that does not exist, and
an index that is down. Folding those into "no results" would answer three
questions with one wrong answer.
"""
from __future__ import annotations

from uuid import UUID

from fastapi.responses import HTMLResponse
from fastapi import Request

from . import console_data
from .console_data import _Missing, label
from .dossiers import DossierError
from .search_index import SearchUnavailable
from .models import Document, DocumentText


def dossier_choices(session) -> list[dict]:
    """The dossiers to pick from, with how many documents each holds."""
    from . import dossiers

    return dossiers.listing(session)


def scope_ids(session, dossier: str):
    """The chosen scope as ids, or None for every dossier.

    Raises ``DossierError`` for an unknown name — an empty result and a typo'd
    scope look identical to a reader, and one of them means "nothing matched".
    """
    from . import dossiers

    ids = dossiers.resolve(session, dossier)
    return None if ids is None else [str(i) for i in ids]


def _samenvatting(rij) -> dict | None:
    """De samenvatting met haar herkomst, of None.

    De herkomst gaat mee omdat dit de enige tekst in dit systeem is die niet
    terug te voeren is op iets dat is opgeslagen. Wie hem leest hoort te weten
    dat een model hem schreef, welk model, en wanneer.
    """
    if rij is None:
        return None
    from .summaries import is_citation

    return {"tekst": rij.text, "model": rij.model,
            "citaat": is_citation(rij.model),
            "wanneer": rij.created_at.strftime("%Y-%m-%d")}


def _rank(index, embedder, q: str, size: int, only, topic):
    """De rangschikking voor deze vraag, en hoe hij tot stand kwam.

    Met een embedder wordt de vraag zélf geëmbed en doet `hybrid_search` het
    werk: lexicale treffers en vectorburen door RRF gefuseerd, daarna op cosinus
    geordend. Dat is wat "stel een vraag" van "typ een trefwoord" onderscheidt —
    een vraag bevat zelden de woorden die in het antwoord staan.

    Zonder embedder blijft het BM25, en dat staat er dan ook bij. Stil
    terugvallen op iets zwakkers is erger dan het niet hebben: dan wijt iemand
    de magere uitslag aan het corpus.
    """
    if embedder is None:
        return index.search(q, size=size, only=only, topic=topic), "lexicaal"
    from .hybrid import hybrid_search

    return (hybrid_search(index, embedder, q, size=size, only=only, topic=topic),
            "semantisch + lexicaal")


def mount(router, session_factory, search_index, TEMPLATES, mag_lezen=None,
          embedder=None) -> None:
    @router.get("/search", response_class=HTMLResponse, include_in_schema=False)
    def search(request: Request, q: str = "", size: int = 10,
               dossier: str = "", topic: str = ""):
        """Search the pseudonymised index — the claim this project rests on.

        The fragment comes from the STORED pseudonymised text, so what you read
        is a quotation of what the index actually holds. A fragment taken from a
        source document would look the same and prove the opposite.
        """
        if mag_lezen is not None:
            mag_lezen(request)
        hits, fout, keuzes, manier = [], "", [], ""
        with session_factory() as session:
            keuzes = dossier_choices(session)
        if q and search_index is None:
            fout = "Deze instantie draait zonder zoekindex."
        elif q and not dossier:
            # Niet stilletjes alles doorzoeken: dat is precies wat deze change
            # onmogelijk maakt.
            fout = "Kies eerst een dossier, of 'alle dossiers'."
        elif q:
            raw = []
            try:
                with session_factory() as session:
                    only = scope_ids(session, dossier)
            except DossierError as exc:
                fout = str(exc)
            else:
                try:
                    raw, manier = _rank(search_index, embedder, q, size, only,
                                        topic or None)
                except SearchUnavailable:
                    # Niets wat de lezer kan oplossen, en niets mis met zijn
                    # vraag. Zeg dat, en zeg wat er nog wél werkt -- anders
                    # leest een storing als een fout van de zoeker.
                    fout = ("Zoeken kan nu niet: de zoekindex is onbereikbaar. "
                            "Dit ligt niet aan je zoekopdracht. Documenten, "
                            "eerder berekende onderwerpen en samenvattingen "
                            "blijven gewoon te openen; probeer het zoeken later "
                            "opnieuw.")
                except Exception as exc:                 # een afgewezen vraag
                    fout = f"De zoekopdracht werd afgewezen: {type(exc).__name__}"
            if raw:
                with session_factory() as session:
                    from .summaries import by_document

                    ids = [UUID(str(h.document_id)) for h in raw]
                    samenvattingen = by_document(session, ids)
                    for h in raw:
                        doc_id = UUID(str(h.document_id))
                        row = session.get(DocumentText, doc_id)
                        hits.append({
                            "id": str(doc_id),
                            "key": label(session.get(Document, doc_id) or _Missing()),
                            "score": round(float(h.score), 2),
                            "fragment": console_data.fragment(
                                row.anonymized_text if row else "", q),
                            # Naast het fragment, nooit ervoor in de plaats: het
                            # fragment is een citaat dat je kunt terugvinden, de
                            # samenvatting is een bewering van een model.
                            "samenvatting": _samenvatting(samenvattingen.get(doc_id)),
                        })
        onderwerp = ""
        if topic:
            # De naam erbij, want een uuid in een badge zegt een lezer niets en
            # "binnen een onderwerp" zonder wélk onderwerp is misleidender dan
            # niets zeggen.
            from uuid import UUID as _UUID

            from .models import Topic
            from .topics import display_name

            with session_factory() as session:
                try:
                    gevonden = session.get(Topic, _UUID(topic))
                except ValueError:
                    gevonden = None
            onderwerp = display_name(gevonden) if gevonden else "onbekend onderwerp"
        return TEMPLATES.TemplateResponse(request, "search.html", {
            "q": q, "hits": hits, "fout": fout, "dossier": dossier,
            "manier": manier,
            "dossiers": keuzes, "suggested": console_data.SUGGESTED,
            "topic": topic, "onderwerp": onderwerp,
            "searchable": search_index is not None})
