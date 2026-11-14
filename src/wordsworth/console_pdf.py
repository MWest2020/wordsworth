# SPDX-License-Identifier: MIT
"""Whether the document page can offer the PDF views (console-pdf-views).

The page links ``GET /documents/{id}/redacted.pdf`` when that route would
serve it, and otherwise says why not in words. A link that leads to a 409 is a
dead end; a sentence that names the reason is not.

This reads availability, never permission. Who may fetch the PDF, or reveal one
with a grant, is decided by the API routes the browser calls with the console
cookie: the same ``_guard_corpus_read``, the same ``authorize()``. Nothing here
is a second door.

The box-map check is the route's own (``pdf_redaction.box_map_status``), so the
link and the route cannot disagree about it. What only a render can tell (a
degenerate box map, 409; the key service, 503) the route still refuses, and the
page shows that refusal.
"""
from __future__ import annotations

from uuid import UUID

from .audit import current_state
from .models import Document
from .pdf_redaction import NO_BOX_MAP, STALE, box_map_status, current_lists_hash
from .states import State

__all__ = ["DELETED", "NO_BOX_MAP", "NO_STORE", "STALE", "current_lists_hash",
           "state"]

#: No object store: the PDF routes are not mounted on this installation.
NO_STORE = "no-store"
#: A deleted document: the routes answer 410 and its box map is gone with it.
DELETED = "deleted"
#: Reason codes and the sentence the page shows for each.
REASONS = {
    NO_STORE: "PDF's zijn op deze installatie niet beschikbaar.",
    DELETED: "Dit document is verwijderd.",
    NO_BOX_MAP: ("Nog geen boxmap voor dit document: de gelakte PDF bestaat "
                 "pas na pseudonimisering in omkeerbare modus (reanonymize "
                 "bouwt er een)."),
    STALE: ("De boxmap is verouderd: de detectielijsten zijn veranderd sinds "
            "hij is gemaakt. Reanonymize ververst hem; tot dan worden de "
            "gelakte PDF en de onthulling als PDF niet aangeboden."),
}


def state(session, document_id: UUID, lists_hash: str | None, *,
          pdf_views: bool = True) -> dict | None:
    """``None`` for an unknown document (no PDF block at all);
    ``{"available": True}``; or ``{"available": False, "reason": code,
    "why": sentence}`` with ``code`` one of ``DELETED``, ``NO_STORE``,
    ``NO_BOX_MAP`` and ``STALE``. ``pdf_views`` is whether the PDF routes
    exist (an object store is configured)."""
    if session.get(Document, document_id) is None:
        return None
    if current_state(session, document_id) == State.DELETED:
        return _not(DELETED)
    if not pdf_views:
        return _not(NO_STORE)
    _, why = box_map_status(session, document_id, lists_hash)
    return _not(why) if why else {"available": True}


def _not(code: str) -> dict:
    return {"available": False, "reason": code, "why": REASONS[code]}
