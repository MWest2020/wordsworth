"""Structured (JSON) logging for pipeline transitions.

One line per transition, machine-parseable and greppable without an external
collector (sovereign — no external telemetry). The log message *is* the JSON,
so there is no separate formatter to keep in sync: whatever is emitted is what
gets parsed. Operators attach their own handler, or call configure_logging()."""
from __future__ import annotations

import json
import logging
import sys
from typing import Any
from uuid import UUID

logger = logging.getLogger("wordsworth.pipeline")

_configured = False


def configure_logging(stream: Any = None) -> None:
    """Attach a stderr handler emitting the raw JSON line. Idempotent, so
    repeated calls (e.g. per app instance) never duplicate output."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    _configured = True


def log_transition(
    *,
    document_id: UUID | str,
    from_state: str | None,
    to_state: str,
    step: str,
    duration_ms: float | None,
    level: str = "info",
) -> str:
    """Emit and return one JSON log line for a state transition. The failed
    state logs at error level; everything else at info."""
    line = json.dumps(
        {
            "event": "transition",
            "document_id": str(document_id),
            "step": step,
            "from": from_state,
            "to": to_state,
            "duration_ms": duration_ms,
            "level": level,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    logger.log(logging.ERROR if level == "error" else logging.INFO, line)
    return line


def log_retry(*, what: str, attempt: int, attempts: int, error: BaseException,
              delay_s: float | None) -> str:
    """One JSON line per retried transient failure, and one when the budget runs
    out (`delay_s` None). The exception's CLASS, never its message: a message
    can quote a fragment of the document it failed on (measurement 01, finding
    4). A retry that leaves no trace cannot be told apart from a call that
    never failed -- which is what hoge-beschikbaarheid 3.2.4 ran into."""
    exhausted = delay_s is None
    line = json.dumps(
        {
            "event": "retry_exhausted" if exhausted else "retry",
            "what": what,
            "attempt": attempt,
            "of": attempts,
            "error": type(error).__name__,
            "delay_s": delay_s,
            "level": "error" if exhausted else "warning",
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    logger.log(logging.ERROR if exhausted else logging.WARNING, line)
    return line


def log_topic_label(*, topic_id: UUID | str, outcome: str,
                    error: BaseException | None = None) -> str:
    """One JSON line per label the console button started (topic-labels-llm):
    the topic and `labelled`, `rejected`, `no_summaries` or `failed`. Through
    this logger because `configure_logging` is what production turns on; a
    logger of its own stayed at WARNING and printed nothing. Never the label
    text, and of an error only its CLASS: a database error carries the bound
    parameters, and those are the label."""
    line = json.dumps(
        {
            "event": "topic_label",
            "topic_id": str(topic_id),
            "outcome": outcome,
            "error": type(error).__name__ if error is not None else None,
            "level": "warning" if error is not None else "info",
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    logger.log(logging.WARNING if error is not None else logging.INFO, line)
    return line
