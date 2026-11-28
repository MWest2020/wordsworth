"""The token bucket per calling service and the coarse 429 audit on
``POST /v1/originals/{document_id}/open`` (design.md "The rate limit", "The
429 audit"). Checked inside the route, after the purpose and query are
validated, so the response order is 401, 422, 429, then the rest of
``api_open.py``'s table.

Every ``service_state`` write (the bucket, the counter, the refusal window)
is its own short transaction. A refusal's audit record, when one is due, is
written in a transaction of its own after that one commits -- never while a
``service_state`` row is held, and never together with lock 4782 (design.md
"Service-only state": the lock order of ``key-service-pseudonymise``)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from . import audit, state


@dataclass(frozen=True)
class Decision:
    """Outcome of one ``check``. ``retry_after`` is whole seconds, 0 when
    allowed."""

    allowed: bool
    retry_after: int


def check(session_factory, *, caller: str, rate_per_minute: float, burst: float,
          now: datetime | None = None) -> Decision:
    """Takes one token from ``caller``'s bucket. On a refusal, records it
    (the counter, always; the audit, lazily) before returning."""
    rate_per_second = rate_per_minute / 60.0
    with session_factory() as session:
        allowed, tokens = state.take_token(session, caller, rate_per_second, burst, now=now)
        session.commit()
    if allowed:
        return Decision(allowed=True, retry_after=0)

    with session_factory() as session:
        state.increment_refusal_counter(session, caller=caller, reason="rate", now=now)
        window = state.record_refusal_window(session, caller=caller, now=now)
        session.commit()

    if window["count"] == 1:
        with session_factory() as session:
            if "prev_window_start" in window:
                audit.append_access(
                    session, event="open_refused_summary", service_caller=caller,
                    document_id=None,
                    payload={"window_start": window["prev_window_start"],
                             "count": window["prev_count"]})
            audit.append_access(
                session, event="open_refused", service_caller=caller,
                document_id=None, payload={"reason": "rate"})
            session.commit()

    retry_after = max(1, math.ceil((1.0 - tokens) / rate_per_second))
    return Decision(allowed=False, retry_after=retry_after)
