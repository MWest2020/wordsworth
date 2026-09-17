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


def mount(router, session_factory, search_index, TEMPLATES) -> None:
    @router.get("/search", response_class=HTMLResponse, include_in_schema=False)
    def search(request: Request, q: str = "", size: int = 10,
               dossier: str = ""):
        """Search the pseudonymised index — the claim this project rests on.

        The fragment comes from the STORED pseudonymised text, so what you read
        is a quotation of what the index actually holds. A fragment taken from a
        source document would look the same and prove the opposite.
        """
        hits, fout, keuzes = [], "", []
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
                    raw = search_index.search(q, size=size, only=only)
                except Exception as exc:                 # index down, query bad
                    fout = f"De zoekindex gaf een fout: {type(exc).__name__}"
            if raw:
                with session_factory() as session:
                    for h in raw:
                        doc_id = UUID(str(h.document_id))
                        row = session.get(DocumentText, doc_id)
                        hits.append({
                            "id": str(doc_id),
                            "key": label(session.get(Document, doc_id) or _Missing()),
                            "score": round(float(h.score), 2),
                            "fragment": console_data.fragment(
                                row.anonymized_text if row else "", q),
                        })
        return TEMPLATES.TemplateResponse(request, "search.html", {
            "q": q, "hits": hits, "fout": fout, "dossier": dossier,
            "dossiers": keuzes, "suggested": console_data.SUGGESTED,
            "searchable": search_index is not None})
