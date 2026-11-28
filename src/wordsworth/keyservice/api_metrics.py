"""``GET /v1/metrics`` (design.md "GET /v1/metrics"): opens per calling
service and purpose, counted from ``access_audit`` at scrape time, and
refusals per calling service and reason, read from ``service_state``'s
counter rows. No value, document id or object key in the output -- who
opens how much is not for anyone who can reach the port, hence this route
is mounted under ``/v1/`` and covered by the same ``ServiceTokenMiddleware``
as every other route, with no change to that middleware. Never
rate-limited: the app mounts no path-keyed limiter middleware, so there is
no rule for this route to be exempt from."""
from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text
from starlette.responses import PlainTextResponse

from . import state
from .db import make_engine, make_session_factory

router = APIRouter()

#: Prometheus text exposition content type.
CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

_OPENS_SQL = text(
    "SELECT service_caller, payload->>'purpose' AS purpose, count(*) AS n "
    "FROM access_audit WHERE event = 'open' "
    "GROUP BY service_caller, payload->>'purpose'")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _session_factory(request: Request):
    app = request.app
    if app.state.session_factory is None:
        if app.state.engine is None:
            app.state.engine = make_engine()
        app.state.session_factory = make_session_factory(app.state.engine)
    return app.state.session_factory


@router.get("/v1/metrics")
def metrics(request: Request) -> PlainTextResponse:
    session_factory = _session_factory(request)
    with session_factory() as session:
        opens = list(session.execute(_OPENS_SQL))
        refusals = state.refusal_counters(session)

    lines: list[str] = [
        "# HELP keyservice_opens_total Opens by calling service and purpose.",
        "# TYPE keyservice_opens_total counter",
    ]
    lines += [
        f'keyservice_opens_total{{caller="{_escape(row.service_caller)}",'
        f'purpose="{_escape(row.purpose or "")}"}} {row.n}'
        for row in opens
    ]
    lines += [
        "# HELP keyservice_open_refusals_total Opens refused by the rate "
        "limit, by calling service and reason.",
        "# TYPE keyservice_open_refusals_total counter",
    ]
    lines += [f"{key} {value}" for key, value in refusals]
    return PlainTextResponse("\n".join(lines) + "\n", media_type=CONTENT_TYPE)
