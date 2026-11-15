# SPDX-License-Identifier: MIT
"""The 55-route inventory (api-corpus-read-gate, design.md "Inventory") as
data, and the walker that compares it against a running application.

A policy names the check a route requires: ``corpus-read``, ``grant-read``,
``grant-admin`` and ``delete`` are declared or body-called guards that answer
403; ``grant`` is decided by the grant presented, not by who the caller is;
``any-key`` is any authenticated caller (or, with auth off, anybody);
``open`` needs no key at all.
"""
from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter, signature
from typing import Callable

from fastapi.routing import APIRoute
from starlette.routing import Mount, Route, WebSocketRoute

from wordsworth import read_gate


@dataclass(frozen=True)
class Row:
    method: str
    path: str
    policy: str
    reason: str
    #: Whether the policy is declared on the route (`dependencies=[Depends(...)]`,
    #: visible to `read_gate.gate_of`) rather than called from the route's body.
    #: Only corpus-read, grant-read and the one declared grant-admin row are;
    #: the ten routes that keep calling `_guard_grant_admin` from their body are
    #: not, and declaration is not meaningful for any other policy.
    declared: bool = True


# --- API -------------------------------------------------------------------
_API_READ = [
    Row("GET", "/documents/{document_id}/state", "corpus-read", "which documents exist"),
    Row("GET", "/documents/{document_id}", "corpus-read", "every audit payload"),
    Row("GET", "/documents/{document_id}/anonymized", "corpus-read", "the text"),
    Row("GET", "/documents/{document_id}/redacted.pdf", "corpus-read", "the document"),
    Row("GET", "/export/anonymized.zip", "corpus-read", "every text"),
    Row("GET", "/search", "corpus-read", "ids, scores, object keys, passage"),
    Row("GET", "/hybrid", "corpus-read", "same"),
    Row("GET", "/ask", "corpus-read", "a generated answer with citations"),
    Row("GET", "/export/ranking.csv", "corpus-read", "rank, id, score, object key"),
    Row("GET", "/dossiers/{dossier_id}/topics", "corpus-read", "what a dossier is about"),
    Row("GET", "/grants/{grant_id}", "grant-read", "recipient, types, document id"),
]
_API_WRITE = [
    Row("POST", "/documents/{document_id}/feedback", "corpus-read", "writes on the audit chain"),
    Row("POST", "/dossiers/{dossier_id}/topics", "corpus-read", "replaces every topic"),
    Row("PATCH", "/topics/{topic_id}", "corpus-read", "renames what every reader sees"),
    Row("POST", "/topics/{topic_id}/label", "corpus-read", "labels one topic"),
    Row("POST", "/dossiers/{dossier_id}/summaries", "corpus-read", "makes summaries"),
    Row("POST", "/reprocess", "corpus-read", "problems keyed by document id"),
]
_API_OTHER = [
    Row("GET", "/roles", "grant-admin", "roles decide what a grant reveals",
        declared=False),
    Row("POST", "/roles", "grant-admin", "same", declared=False),
    Row("PUT", "/roles/{name}/types", "grant-admin", "same", declared=False),
    Row("POST", "/roles/{name}/deactivate", "grant-admin", "same", declared=False),
    Row("POST", "/roles/{name}/activate", "grant-admin", "same", declared=False),
    Row("POST", "/grants", "grant-admin", "mints a grant", declared=False),
    Row("POST", "/grants/{grant_id}/revoke", "grant-admin", "revokes a grant",
        declared=False),
    Row("POST", "/datasets/pseudonymize", "grant-admin", "a token lookup"),
    Row("DELETE", "/documents/{document_id}", "delete", "irreversible"),
    Row("DELETE", "/dossiers/{dossier_id}", "delete", "irreversible"),
    Row("POST", "/documents/{document_id}/reveal", "grant", "decided by the grant"),
    Row("POST", "/documents/{document_id}/reveal.pdf", "grant", "decided by the grant"),
]
_API_UNDECIDED = [
    Row("POST", "/ingest", "any-key", "issue #431; not decided here"),
]
_API_OPEN = [
    Row("GET", "/health", "open", "liveness probe"),
    Row("GET", "/metrics", "open", "ops probe, api-key-auth spec exempt"),
    Row("GET", "/", "any-key", "redirect or {'detail': 'see /docs'}"),
    Row("GET", "/openapi.json", "any-key", "describes the routes, not the corpus"),
    Row("GET", "/docs", "any-key", "same"),
    Row("GET", "/docs/oauth2-redirect", "any-key", "same"),
    Row("GET", "/redoc", "any-key", "same"),
]

# --- Console -----------------------------------------------------------------
_CONSOLE_READ = [
    Row("GET", "/console", "corpus-read", "dossier picker", declared=False),
    Row("GET", "/console/dossier", "corpus-read", "same", declared=False),
    Row("GET", "/console/documents", "corpus-read", "alle documenten", declared=False),
    Row("GET", "/console/documents/{document_id}", "corpus-read", "one document",
        declared=False),
    Row("GET", "/console/search", "corpus-read", "search page", declared=False),
    Row("GET", "/console/topics", "corpus-read", "topics page", declared=False),
    Row("GET", "/console/feedback", "corpus-read", "feedback page", declared=False),
    Row("POST", "/console/topics", "corpus-read", "recompute topics", declared=False),
    Row("POST", "/console/topics/{topic_id}/label", "corpus-read", "label a topic",
        declared=False),
    Row("GET", "/console/combinations", "corpus-read", "declared combinations + reach",
        declared=False),
    Row("POST", "/console/combinations", "corpus-read", "declares one, writes",
        declared=False),
]
_CONSOLE_OTHER = [
    Row("GET", "/console/roles", "grant-admin", "beheren", declared=False),
    Row("POST", "/console/roles", "grant-admin", "same", declared=False),
    Row("POST", "/console/roles/switch", "grant-admin", "same", declared=False),
]
_CONSOLE_OPEN = [
    Row("GET", "/console/login", "open", "nobody can bring a key here"),
    Row("POST", "/console/login", "open", "same"),
    Row("GET", "/console/static", "open", "fonts, console.js, login's own assets"),
    Row("GET", "/console/logout", "any-key", "clears the caller's own cookie"),
]

ROWS: list[Row] = (_API_READ + _API_WRITE + _API_OTHER + _API_UNDECIDED + _API_OPEN
                   + _CONSOLE_READ + _CONSOLE_OTHER + _CONSOLE_OPEN)

#: `create_app` parameters that mount no route of their own — either pure
#: middleware/behaviour knobs, or (access_verifier) one of two equivalent ways
#: to satisfy a condition the fixture already satisfies with `api_keys`.
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


def unaccounted_params(create_app: Callable, passed: dict) -> list[str]:
    """Which `create_app` parameters neither the fixture passes nor
    `NO_ROUTE_PARAMS` names — the signature check (design.md, "The walk",
    first bullet)."""
    names = [
        p.name for p in signature(create_app).parameters.values()
        if p.kind in (Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY)
    ]
    return [n for n in names if n not in passed and n not in NO_ROUTE_PARAMS]


class UnknownRouteType(TypeError):
    pass


class WebSocketRouteFound(TypeError):
    pass


def collect_routes(app) -> dict[tuple[str, str], object]:
    """Every `(method, path)` the application answers, mapped to the route
    object that declares it. Descends into every included router and every
    `Mount` of an application; a `Mount` of a plain ASGI app (static files) is
    one row. `HEAD` folds into `GET` of the same route object. Raises on a
    route object of an unknown type or a `WebSocketRoute` — both mean the walk
    stopped seeing, which is worse than a wrong expectation."""
    out: dict[tuple[str, str], object] = {}

    def walk(routes) -> None:
        for route in routes:
            if isinstance(route, WebSocketRoute):
                raise WebSocketRouteFound(route.path)
            if isinstance(route, APIRoute):
                methods = set(route.methods)
                has_get = "GET" in methods
                for method in methods:
                    if method == "OPTIONS" or (method == "HEAD" and has_get):
                        continue
                    out[(method, route.path)] = route
                continue
            if isinstance(route, Mount):
                if hasattr(route.app, "routes"):
                    walk(route.app.routes)
                else:
                    out[("GET", route.path)] = route
                continue
            if isinstance(route, Route):
                methods = set(route.methods or ())
                has_get = "GET" in methods
                for method in methods:
                    if method == "OPTIONS" or (method == "HEAD" and has_get):
                        continue
                    out[(method, route.path)] = route
                continue
            original_router = getattr(route, "original_router", None)
            if original_router is not None:
                walk(original_router.routes)
                continue
            raise UnknownRouteType(f"{type(route).__name__} at {route!r}")

    walk(app.routes)
    return out


def gate_name(route) -> str | None:
    return read_gate.gate_of(route)
