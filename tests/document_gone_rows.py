# SPDX-License-Identifier: MIT
"""For every route whose path contains `{document_id}`, its answer for a
deleted document (deleted-document-answers-410, design.md decision 6):
``410``, ``record`` (200, what a deletion keeps), ``rerun`` (DELETE finishes
leftover work, not a 410), ``reveal-api`` (governed by `reveal-authorize-
first`, #494, asserted by its own tests, not here) or ``page`` (the console
page still opens). The walk that holds an application against these rows is
in ``document_gone_inventory.py``.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoneRow:
    method: str
    path: str
    answer: str  # "410" | "record" | "rerun" | "reveal-api" | "page"


ROWS: list[GoneRow] = [
    GoneRow("GET", "/documents/{document_id}/state", "record"),
    GoneRow("GET", "/documents/{document_id}", "record"),
    GoneRow("GET", "/documents/{document_id}/anonymized", "410"),
    GoneRow("GET", "/documents/{document_id}/redacted.pdf", "410"),
    GoneRow("POST", "/documents/{document_id}/feedback", "410"),
    GoneRow("DELETE", "/documents/{document_id}", "rerun"),
    GoneRow("POST", "/documents/{document_id}/reveal", "reveal-api"),
    GoneRow("POST", "/documents/{document_id}/reveal.pdf", "reveal-api"),
    GoneRow("GET", "/console/documents/{document_id}", "page"),
]
