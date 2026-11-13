# SPDX-License-Identifier: MIT
"""Whether the document page can link the redacted PDF (console-pdf-views).

The page links ``GET /documents/{id}/redacted.pdf`` when that route would
serve it, and otherwise says why not in words. A link that leads to a 409 is a
dead end; a sentence that names the reason is not.

This reads availability, never permission. Who may fetch the PDF, or reveal one
with a grant, is decided by the API routes the browser calls with the console
cookie: the same ``_guard_corpus_read``, the same ``authorize()``. Nothing here
is a second door.

The two reasons are the two the route itself checks before rendering
(``api.py``, ``redacted_pdf``): no box map, or a box map made under detection
lists other than the ones currently configured. The comparison is the same one:
the stored ``lists_hash`` against the lists as configured now, not against the
document's own audit trail.
"""
from __future__ import annotations

from uuid import UUID

from .models import BoxMap

#: Reason codes and the sentence the page shows for each.
NO_BOX_MAP = "no-box-map"
STALE = "stale"
REASONS = {
    NO_BOX_MAP: ("Nog geen boxmap voor dit document: de gelakte PDF bestaat "
                 "pas na pseudonimisering in omkeerbare modus (reanonymize "
                 "bouwt er een)."),
    STALE: ("De boxmap is verouderd: de detectielijsten zijn veranderd sinds "
            "hij is gemaakt. Reanonymize ververst hem; tot dan wordt de "
            "gelakte PDF niet geleverd."),
}


def lists_hash() -> str:
    """The hash of the detection lists as currently configured: the value the
    redacted-PDF route compares a box map against."""
    from .config import settings
    from .detection_lists import DetectionLists

    return DetectionLists.load(settings.detection_lists_dir).hash


def state(session, document_id: UUID, current_lists_hash: str) -> dict:
    """``{"available": True}``, or ``{"available": False, "reason": code,
    "why": sentence}`` with ``code`` one of ``NO_BOX_MAP`` and ``STALE``."""
    box_map = session.get(BoxMap, document_id)
    if box_map is None:
        return _not(NO_BOX_MAP)
    if box_map.lists_hash != current_lists_hash:
        return _not(STALE)
    return {"available": True}


def _not(code: str) -> dict:
    return {"available": False, "reason": code, "why": REASONS[code]}
