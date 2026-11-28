"""``service_state``: state that only the key service has, that is not a
copy of a wordsworth table and not derived from the service's own audit
stream (design.md "Service-only state: service_state"). Three kinds share one
table: the rate-limit bucket (``rate_bucket``), the refusal window
(``refusal_window``) and a Prometheus counter (``counter``). This is the
only module that writes it -- it never names the service's other,
hash-chained stream (``audit.py``), which ``limits.py`` writes to instead.

Every write is one statement on the caller's row (``INSERT ... ON CONFLICT
DO UPDATE ... RETURNING``), referencing the pre-update row through the
table's own alias (``s``) inside ``SET`` and never through a CTE computed
before the statement -- the same shape as ``wordsworth.rate_limit_pg``, so
two replicas writing the same row are serialised by the row lock, not by
luck. The clock is the database server's ``now()`` unless a test passes one
explicitly (``COALESCE(:now, now())``), never a replica's clock."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from .models import KeyServiceBase

#: design.md "The 429 audit": a fixed window, the same for every caller --
#: not a setting.
WINDOW_SECONDS = 60


class ServiceState(KeyServiceBase):
    """One row per (``kind``, ``key``). ``counter`` is used by the
    ``counter`` kind only; ``data`` by ``rate_bucket`` and
    ``refusal_window`` only (design.md "Service-only state")."""

    __tablename__ = "service_state"

    kind: Mapped[str] = mapped_column(String, primary_key=True)
    key: Mapped[str] = mapped_column(String, primary_key=True)
    counter: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


_TAKE_TOKEN_SQL = text("""
INSERT INTO service_state AS s (kind, key, counter, data, updated_at)
VALUES ('rate_bucket', :caller, 0,
        jsonb_build_object(
            'tokens', CASE WHEN :burst >= 1 THEN :burst - 1 ELSE :burst END,
            'allowed', :burst >= 1),
        COALESCE(CAST(:now AS timestamptz), now()))
ON CONFLICT (kind, key) DO UPDATE SET
    data = jsonb_build_object(
        'allowed',
        LEAST(:burst, (s.data->>'tokens')::double precision
              + EXTRACT(EPOCH FROM COALESCE(CAST(:now AS timestamptz), now())
                        - s.updated_at) * :rate) >= 1,
        'tokens',
        LEAST(:burst, (s.data->>'tokens')::double precision
              + EXTRACT(EPOCH FROM COALESCE(CAST(:now AS timestamptz), now())
                        - s.updated_at) * :rate)
        - CASE WHEN LEAST(:burst, (s.data->>'tokens')::double precision
                          + EXTRACT(EPOCH FROM COALESCE(CAST(:now AS timestamptz), now())
                                    - s.updated_at) * :rate) >= 1
               THEN 1 ELSE 0 END),
    updated_at = COALESCE(CAST(:now AS timestamptz), now())
RETURNING (data->>'allowed')::boolean AS allowed,
          (data->>'tokens')::double precision AS tokens
""")


def take_token(session: Session, caller: str, rate: float, burst: float, *,
                now: datetime | None = None) -> tuple[bool, float]:
    """One token from ``caller``'s bucket (``kind = rate_bucket``). Returns
    ``(allowed, tokens left)`` -- ``limits.py`` turns a refusal's tokens into
    the ``Retry-After`` seconds. The caller commits."""
    allowed, tokens = session.execute(
        _TAKE_TOKEN_SQL,
        {"caller": caller, "rate": rate, "burst": burst, "now": now}).one()
    return allowed, tokens


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


_INCREMENT_COUNTER_SQL = text("""
INSERT INTO service_state AS s (kind, key, counter, data, updated_at)
VALUES ('counter', :key, 1, NULL, COALESCE(CAST(:now AS timestamptz), now()))
ON CONFLICT (kind, key) DO UPDATE SET
    counter = s.counter + 1, updated_at = COALESCE(CAST(:now AS timestamptz), now())
RETURNING counter
""")


def increment_refusal_counter(session: Session, *, caller: str, reason: str,
                               now: datetime | None = None) -> int:
    """``keyservice_open_refusals_total{caller,reason}`` -- the metric name
    and its label set double as the row's ``key`` (design.md "Service-only
    state"), so ``api_metrics.py`` renders it without reassembling labels.
    The caller commits."""
    key = (f'keyservice_open_refusals_total{{caller="{_escape_label(caller)}",'
           f'reason="{_escape_label(reason)}"}}')
    return session.execute(_INCREMENT_COUNTER_SQL, {"key": key, "now": now}).scalar_one()


_RECORD_REFUSAL_SQL = text("""
INSERT INTO service_state AS s (kind, key, counter, data, updated_at)
VALUES ('refusal_window', :caller, 0,
        jsonb_build_object(
            'window_start', COALESCE(CAST(:now AS timestamptz), now()), 'count', 1),
        COALESCE(CAST(:now AS timestamptz), now()))
ON CONFLICT (kind, key) DO UPDATE SET
    data = CASE
        WHEN (s.data->>'window_start')::timestamptz
              > COALESCE(CAST(:now AS timestamptz), now()) - make_interval(secs => :window)
        THEN jsonb_build_object('window_start', s.data->>'window_start',
                                 'count', (s.data->>'count')::int + 1)
        ELSE jsonb_build_object(
            'window_start', COALESCE(CAST(:now AS timestamptz), now()), 'count', 1,
            'prev_window_start', s.data->>'window_start',
            'prev_count', (s.data->>'count')::int)
    END,
    updated_at = COALESCE(CAST(:now AS timestamptz), now())
RETURNING data
""")


def record_refusal_window(session: Session, *, caller: str,
                           now: datetime | None = None) -> dict[str, Any]:
    """Adds one refusal to the caller's current window, or starts a new one
    (design.md "The 429 audit"). The returned ``data``'s ``count`` is 1
    exactly when this call started the window; ``prev_window_start`` and
    ``prev_count`` are present only then, and only when a previous window
    existed. The caller commits."""
    return session.execute(
        _RECORD_REFUSAL_SQL,
        {"caller": caller, "now": now, "window": WINDOW_SECONDS}).scalar_one()


_REFUSAL_COUNTERS_SQL = text(
    "SELECT key, counter FROM service_state WHERE kind = 'counter' ORDER BY key")


def refusal_counters(session: Session) -> list[tuple[str, int]]:
    """Every ``counter`` row: ``(rendered Prometheus key, value)`` pairs,
    read at scrape time by ``api_metrics.py``."""
    return [(row.key, row.counter) for row in session.execute(_REFUSAL_COUNTERS_SQL)]
