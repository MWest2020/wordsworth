# SPDX-License-Identifier: MIT
"""The walker that holds an application against the rows of
``document_gone_rows.py``: every route whose path contains `{document_id}`
must have a row, and every row must name a route the application answers.
"""
from __future__ import annotations

from document_gone_rows import ROWS
from route_inventory import collect_routes

HAS_DOCUMENT_ID = "{document_id}"


def document_id_routes(app) -> set[tuple[str, str]]:
    return {(method, path) for method, path in collect_routes(app)
            if HAS_DOCUMENT_ID in path}


def missing_gone_rows(app, rows=ROWS) -> set:
    """`{document_id}` routes the application answers that have no row."""
    return document_id_routes(app) - {(r.method, r.path) for r in rows}


def orphan_gone_rows(app, rows=ROWS) -> set:
    """Rows for which the application answers no route."""
    return {(r.method, r.path) for r in rows} - document_id_routes(app)
