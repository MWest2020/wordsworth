"""Run report: current-state counts, born-digital share, size distribution.

Because born-digital share and document size are measured by the pipeline
(profiling), the report falls out of the audit data rather than out of a
pre-run assumption."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

_CURRENT_STATES = text(
    """
    SELECT to_state, count(*) AS n FROM (
        SELECT DISTINCT ON (document_id) document_id, to_state
        FROM audit_records ORDER BY document_id, seq DESC
    ) latest GROUP BY to_state
    """
)

_PROFILE_OUTCOMES = text(
    "SELECT to_state, count(*) AS n FROM audit_records "
    "WHERE step = 'profile' GROUP BY to_state"
)

_PROFILE_PAGES = text(
    "SELECT (payload->>'pages')::int AS pages FROM audit_records "
    "WHERE step = 'profile' AND payload ? 'pages'"
)


def run_report(session: Session) -> dict[str, Any]:
    current = {row.to_state: row.n for row in session.execute(_CURRENT_STATES)}
    outcomes = {row.to_state: row.n for row in session.execute(_PROFILE_OUTCOMES)}
    pages = [row.pages for row in session.execute(_PROFILE_PAGES)]

    born = outcomes.get("extractable", 0)
    scanned = outcomes.get("unprocessable_ocr", 0)
    profiled = born + scanned
    share = round(born / profiled, 4) if profiled else None

    page_stats = None
    if pages:
        page_stats = {
            "count": len(pages),
            "sum": sum(pages),
            "min": min(pages),
            "max": max(pages),
            "avg": round(sum(pages) / len(pages), 2),
        }

    return {
        "total_documents": sum(current.values()),
        "current_states": current,
        "profile_outcomes": outcomes,
        "born_digital_share": share,
        "pages": page_stats,
    }
