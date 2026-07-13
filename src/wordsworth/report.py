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

# Wall-clock span of the run, from the first to the last audit record.
_SPAN = text("SELECT min(ts) AS lo, max(ts) AS hi FROM audit_records")

# Per-stage timing: the gap between each transition and the previous one for the
# same document, grouped by step. The first (register) transition has no
# predecessor, so its NULL gap drops out — leaving the real pipeline stages.
_STAGE_TIMING = text(
    """
    SELECT step,
           count(*) AS n,
           avg(dur_ms) AS mean_ms,
           percentile_cont(0.95) WITHIN GROUP (ORDER BY dur_ms) AS p95_ms
    FROM (
        SELECT step,
               EXTRACT(EPOCH FROM (
                   ts - lag(ts) OVER (PARTITION BY document_id ORDER BY seq)
               )) * 1000 AS dur_ms
        FROM audit_records
    ) d
    WHERE dur_ms IS NOT NULL
    GROUP BY step
    """
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

    total = sum(current.values())
    span = session.execute(_SPAN).one()
    elapsed_hours = None
    docs_per_hour = None
    if span.lo is not None and span.hi is not None:
        seconds = (span.hi - span.lo).total_seconds()
        elapsed_hours = round(seconds / 3600, 6)
        if seconds > 0:
            docs_per_hour = round(total / (seconds / 3600), 2)

    stage_timing = {
        row.step: {
            "count": row.n,
            "mean_ms": round(float(row.mean_ms), 3),
            "p95_ms": round(float(row.p95_ms), 3),
        }
        for row in session.execute(_STAGE_TIMING)
    }

    return {
        "total_documents": total,
        "current_states": current,
        "profile_outcomes": outcomes,
        "born_digital_share": share,
        "pages": page_stats,
        "elapsed_hours": elapsed_hours,
        "docs_per_hour": docs_per_hour,
        "stage_timing": stage_timing,
    }
