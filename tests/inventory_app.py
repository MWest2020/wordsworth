# SPDX-License-Identifier: MIT
"""The application the inventory tests walk: ``create_app`` with every
optional backend present, so every route mounts, on cheap stand-ins.

The walk never runs a route. The refusal tests do, but a gate answers before
a route body touches a stand-in, and the few any-key and open bodies that run
only have to return something other than 401 or 403. The DB-backed tests
(``read_gate_world.py``) run the same rows against a seeded Postgres.
"""
from __future__ import annotations

import re

from fastapi.routing import APIRoute

from wordsworth.api import create_app
from wordsworth.embedder import DeterministicEmbedder
from wordsworth.generator import DeterministicGenerator
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.search_index import InMemoryIndex

from route_inventory import require_every_param

KEYS = {"klezer": "lezer", "kuitgever": "uitgever", "kderde": "derde"}


class _Fake:
    def anonymize(self, text: str):
        return None

    def get(self, *a, **kw):
        return None


class _EmptyResult:
    def scalars(self):
        return iter(())

    def scalar_one(self):
        return None


class _FakeSession:
    """Enough for a body-call guard to run (`caller_holds_role` queries before
    refusing) without a database: every query comes back empty."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *a, **kw):
        return _EmptyResult()

    def get(self, *a, **kw):
        return None

    def commit(self):
        pass


def full_app(factory=create_app, **overrides):
    """Every optional backend present. `factory` lets a test hand in a
    `create_app` with a scratch parameter; the parameter check runs first."""
    kwargs = dict(
        session_factory=_FakeSession, search_index=InMemoryIndex(),
        embedder=DeterministicEmbedder(dim=8), generator=DeterministicGenerator(),
        store=InMemoryObjectStore(), anonymizer=_Fake(), key_provider=_Fake(),
        grant_store=_Fake(), anonymizer_factory=lambda s: _Fake(),
        key_provider_factory=lambda s: _Fake(),
        grant_store_factory=lambda s: _Fake(),
        api_keys=KEYS, corpus_read_labels=["lezer"],
        grant_issuer_labels=["uitgever"],
    )
    kwargs.update(overrides)
    require_every_param(factory, kwargs)
    return factory(**kwargs)


def ungated_search_app():
    """The real application with `/search` rebuilt without its gate."""
    app = full_app()
    i, old = next((i, r) for i, r in enumerate(app.router.routes)
                  if isinstance(r, APIRoute) and r.path == "/search")
    app.router.routes[i] = APIRoute(old.path, old.endpoint, methods=old.methods)
    return app


#: A declared gate runs before validation, so any well-formed id works. A
#: body-call guard runs after it, so those rows need a valid body to be reached.
VALID_ID = "11111111-1111-1111-1111-111111111111"
_PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
BODIES = {
    ("POST", "/roles"): {"json": {"name": "x", "allowed_types": ["PERSON"]}},
    ("PUT", "/roles/{name}/types"): {"json": {"allowed_types": ["PERSON"]}},
    ("POST", "/roles/{name}/deactivate"): {"json": {"reason": "x"}},
    ("POST", "/roles/{name}/activate"): {"json": {"reason": "x"}},
    ("POST", "/grants"): {"json": {"recipient": "x", "allowed_types": ["PERSON"]}},
    ("POST", "/console/topics"): {"data": {"dossier": "x"}},
    ("POST", "/console/topics/{topic_id}/label"): {"data": {"dossier": "x"}},
    ("POST", "/console/combinations"): {"data": {"types": "PERSON"}},
    ("POST", "/console/roles"): {"data": {"name": "x"}},
    ("POST", "/console/roles/switch"): {"data": {"name": "x", "aan": "true"}},
}


def call(client, row, key: str | None = "kderde", method: str | None = None):
    """Request `row` as the caller holding `key`, with a valid id and body."""
    path = _PLACEHOLDER.sub(VALID_ID, row.path)
    body = BODIES.get((row.method, row.path), {})
    headers = {"X-API-Key": key} if key else {}
    method = method or row.method
    if "data" in body:
        return client.request(method, path, data=body["data"], headers=headers)
    json_body = body.get("json", {} if method in ("POST", "PATCH", "PUT") else None)
    return client.request(method, path, json=json_body, headers=headers)
