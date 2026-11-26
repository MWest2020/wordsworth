# SPDX-License-Identifier: MIT
"""The walker that holds a running application against the inventory in
``route_rows.py`` (api-corpus-read-gate, design.md "The test that keeps the
inventory true"), and the checks the tests assert on.

Each check returns what is wrong instead of asserting, so the same function
runs on the real application (must come back empty) and on an application
with a scratch change (must not): that is how a test shows the walk would
catch the change, rather than restating what it walks.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from inspect import Parameter, signature
from pathlib import Path
from typing import Callable

from fastapi.routing import APIRoute
from starlette.routing import Mount, Route, WebSocketRoute

from route_rows import ROWS, Row  # noqa: F401  (re-exported for the tests)
from wordsworth import read_gate

#: The framework's own schema routes (`/openapi.json`, `/docs`,
#: `/docs/oauth2-redirect`, `/redoc`): rows, but no registration of ours.
FRAMEWORK_ROUTES = 4

#: `create_app` parameters that mount no route of their own: middleware or
#: behaviour knobs, or (access_verifier) a second way to satisfy a condition
#: the fixture already satisfies with `api_keys`.
NO_ROUTE_PARAMS = {
    "rate_limiters": "adds rate-limit middleware, not a route",
    "key_audit": "where an audit record is written, not whether a route exists",
    "cors_allow_origins": "adds CORS middleware, not a route",
    "access_verifier": "api_keys already satisfies 'keys or identity is not None'",
    "vc_public_key": "narrows a reveal, not whether the route exists",
    "vc_expected_issuer": "same",
    "vc_expected_vct": "same",
    "vc_required": "same",
    "allow_global_grants": "validates a grant body at request time, not route presence",
}


class UnmountedParameter(AssertionError):
    pass


class UnknownRouteType(TypeError):
    pass


class WebSocketRouteFound(TypeError):
    pass


class AnyMethodRoute(TypeError):
    """A Starlette `Route` whose endpoint is an ASGI app (`methods=None`): it
    answers every method, so no row keyed by method can describe it."""


def unaccounted_params(create_app: Callable, passed: dict) -> list[str]:
    """`create_app` parameters neither passed nor named in `NO_ROUTE_PARAMS`."""
    names = [p.name for p in signature(create_app).parameters.values()
             if p.kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)]
    return [n for n in names if n not in passed and n not in NO_ROUTE_PARAMS]


def require_every_param(create_app: Callable, passed: dict) -> None:
    missing = unaccounted_params(create_app, passed)
    if missing:
        raise UnmountedParameter(f"create_app parameters the fixture does not "
                                 f"pass and NO_ROUTE_PARAMS does not name: {missing}")


@dataclass(frozen=True)
class Found:
    """A route as the application serves it: the route object, and the
    dependencies of every `include_router` it sits under."""
    route: object
    include_dependencies: tuple = field(default=())


def _methods(route, path: str) -> list[str]:
    if route.methods is None:
        raise AnyMethodRoute(path)
    methods = set(route.methods)
    return [m for m in methods
            if m != "OPTIONS" and not (m == "HEAD" and "GET" in methods)]


def collect_routes(app) -> dict[tuple[str, str], Found]:
    """Every `(method, path)` the application answers, with the full path: the
    prefix of every `Mount` and every `include_router` it sits under is kept.
    Descends into included routers and mounted applications; a `Mount` of a
    plain ASGI app (static files) is one row. `HEAD` folds into `GET` of the
    same route object. Raises on an unknown route type, a `WebSocketRoute` and
    a route answering every method: each means the walk stopped seeing."""
    out: dict[tuple[str, str], Found] = {}

    def walk(routes, prefix: str, deps: tuple) -> None:
        for route in routes:
            if isinstance(route, WebSocketRoute):
                raise WebSocketRouteFound(prefix + route.path)
            if isinstance(route, (APIRoute, Route)):
                path = prefix + route.path
                for method in _methods(route, path):
                    out[(method, path)] = Found(route, deps)
            elif isinstance(route, Mount):
                if hasattr(route.app, "routes"):
                    walk(route.app.routes, prefix + route.path, deps)
                else:
                    out[("GET", prefix + route.path)] = Found(route, deps)
            elif getattr(route, "original_router", None) is not None:
                ctx = route.include_context
                walk(route.original_router.routes, prefix + ctx.prefix,
                     deps + tuple(ctx.dependencies))
            else:
                raise UnknownRouteType(f"{type(route).__name__} at {route!r}")

    walk(app.routes, "", ())
    return out


def gate_name(found: Found) -> str | None:
    """The gate a route declares, on itself or on a router it is included by."""
    name = read_gate.gate_of(found.route)
    if name is not None:
        return name
    for dep in found.include_dependencies:
        if isinstance(dep.dependency, read_gate.Gate):
            return dep.dependency.name
    return None


def missing_rows(routes: dict, rows=ROWS) -> set:
    """Routes the application answers that have no row."""
    return set(routes) - {(r.method, r.path) for r in rows}


def orphan_rows(routes: dict, rows=ROWS) -> set:
    """Rows for which the application answers no route."""
    return {(r.method, r.path) for r in rows} - set(routes)


def undeclared_gates(routes: dict, rows=ROWS) -> set:
    """Rows that promise a declared gate their route does not declare."""
    return {(r.method, r.path) for r in rows
            if r.declared and r.policy in ("corpus-read", "grant-read", "grant-admin")
            and (r.method, r.path) in routes
            and gate_name(routes[(r.method, r.path)]) != r.policy}


#: Policies under which a route refuses a caller on no list (403).
REFUSING = ("corpus-read", "grant-read", "grant-admin", "delete")

#: The only routes decided by the grant presented rather than by the caller.
#: A row saying `grant` counts as a check only here: the refusal suite never
#: requests a `grant` row, so elsewhere it would be a check nobody verifies.
GRANT_DECIDED = {
    ("POST", "/documents/{document_id}/reveal"),
    ("POST", "/documents/{document_id}/reveal.pdf"),
}

#: The only writing routes no check refuses, each with its reason.
OPEN_WRITES = {
    ("POST", "/console/login"): "nobody can bring a key to the page that asks for one",
}


def ungated_writes(routes: dict, rows=ROWS) -> set:
    """Writing routes (any method but GET and HEAD) whose row names no refusing
    policy and that `OPEN_WRITES` does not name (ingest-requires-corpus-read):
    a write route answering any authenticated caller has to be a decision
    written down here, not a row nobody looked at."""
    return {(r.method, r.path) for r in rows
            if r.method not in ("GET", "HEAD") and r.policy not in REFUSING
            and not (r.policy == "grant" and (r.method, r.path) in GRANT_DECIDED)
            and (r.method, r.path) in routes
            and (r.method, r.path) not in OPEN_WRITES}


_REGISTRATION = re.compile(
    r"@[\w.]+\.(get|post|put|patch|delete|head|options|trace|api_route"
    r"|websocket|websocket_route|route)\("
    r"|\b[\w.]+\.(add_api_route|add_route|add_websocket_route"
    r"|add_api_websocket_route)\("
    # `app.mount("/path", ...)`; not the console modules' own `mount(router, ...)`.
    r"|\.mount\(\s*[\"']")


def count_registrations(src: Path) -> int:
    """Route decorators, `add_*route` calls and path mounts in every `.py`
    file under `src`, subpackages included."""
    return sum(len(_REGISTRATION.findall(p.read_text()))
               for p in sorted(src.rglob("*.py")))


def registration_mismatch(count: int, rows=ROWS) -> int:
    """How far the source count is from the rows minus the framework's own."""
    return count - (len(rows) - FRAMEWORK_ROUTES)
