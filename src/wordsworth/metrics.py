"""Prometheus-text metrics derived from the audit table.

No client dependency: the exposition format is plain text, emitted directly.
Everything comes from the append-only audit table (the single source of truth),
so there is no separate metrics store to keep consistent. Local only — scraping
is the operator's choice; no external telemetry is contacted (sovereign)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

# Prometheus text exposition content type.
CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

# Current state per document = the latest audit record's to_state (derived,
# never a stored column). Same shape as the run report's current-state query.
_CURRENT_STATES = text(
    """
    SELECT to_state, count(*) AS n FROM (
        SELECT DISTINCT ON (document_id) document_id, to_state
        FROM audit_records ORDER BY document_id, seq DESC
    ) latest GROUP BY to_state
    """
)

_TRANSITIONS = text(
    "SELECT step, count(*) AS n FROM audit_records GROUP BY step"
)

_FAILED = text("SELECT count(*) AS n FROM audit_records WHERE to_state = 'failed'")


def _escape(value: str) -> str:
    """Escape a Prometheus label value (backslash, quote, newline)."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _metric(name: str, help_text: str, mtype: str, samples: list[str]) -> list[str]:
    return [f"# HELP {name} {help_text}", f"# TYPE {name} {mtype}", *samples, ""]


def render_metrics(session: Session) -> str:
    """Render the audit-derived metrics in Prometheus text format."""
    states = {row.to_state: row.n for row in session.execute(_CURRENT_STATES)}
    steps = {row.step: row.n for row in session.execute(_TRANSITIONS)}
    failed = session.execute(_FAILED).scalar_one()

    lines: list[str] = []
    lines += _metric(
        "wordsworth_documents_total",
        "Documents by current (derived) state.",
        "gauge",
        [
            f'wordsworth_documents_total{{state="{_escape(s)}"}} {n}'
            for s, n in sorted(states.items())
        ],
    )
    lines += _metric(
        "wordsworth_transitions_total",
        "Audit transitions by pipeline step.",
        "counter",
        [
            f'wordsworth_transitions_total{{step="{_escape(s)}"}} {n}'
            for s, n in sorted(steps.items())
        ],
    )
    lines += _metric(
        "wordsworth_failed_total",
        "Transitions into the failed state.",
        "counter",
        [f"wordsworth_failed_total {failed}"],
    )
    return "\n".join(lines)
