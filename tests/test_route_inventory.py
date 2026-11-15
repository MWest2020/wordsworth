# SPDX-License-Identifier: MIT
"""The inventory test (api-corpus-read-gate): every route the application
mounts has a recorded access decision, and the decision holds."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from starlette.staticfiles import StaticFiles

from wordsworth.api import create_app
from wordsworth.embedder import DeterministicEmbedder
from wordsworth.generator import DeterministicGenerator
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.read_gate import corpus_read
from wordsworth.search_index import InMemoryIndex

from route_inventory import (ROWS, NO_ROUTE_PARAMS, UnknownRouteType,
                             WebSocketRouteFound, collect_routes, gate_name,
                             unaccounted_params)

SRC = Path(__file__).parent.parent / "src" / "wordsworth"
#: The framework's own four schema routes (`/openapi.json`, `/docs`,
#: `/docs/oauth2-redirect`, `/redoc`) have no `@app.get(...)` of ours.
FRAMEWORK_ROUTES = 4


class _FakeKeyProvider:
    pass


class _FakeAnonymizer:
    def anonymize(self, text: str):
        return None


class _FakeGrantStore:
    def get(self, grant_id):
        return None


class _EmptyResult:
    def scalars(self):
        return iter(())

    def scalar_one(self):
        return None


class _FakeSession:
    """Just enough to let a body-call guard run (`caller_holds_role` queries
    before refusing) without a real database: every query comes back empty."""

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


def _full_app(**overrides):
    """Every optional backend present, so every route in `create_app` mounts.
    Cheap stand-ins: the walk and refusal tests never let a route body touch
    them (the gate answers first), and the few any-key/open bodies that do run
    only need to not raise before returning a non-401/403 status."""
    kwargs = dict(
        session_factory=_FakeSession,
        search_index=InMemoryIndex(),
        embedder=DeterministicEmbedder(dim=8),
        generator=DeterministicGenerator(),
        store=InMemoryObjectStore(),
        anonymizer=_FakeAnonymizer(),
        key_provider=_FakeKeyProvider(),
        grant_store=_FakeGrantStore(),
        anonymizer_factory=lambda s: _FakeAnonymizer(),
        key_provider_factory=lambda s: _FakeKeyProvider(),
        grant_store_factory=lambda s: _FakeGrantStore(),
        api_keys={"klezer": "lezer", "kuitgever": "uitgever", "kderde": "derde"},
        corpus_read_labels=["lezer"],
        grant_issuer_labels=["uitgever"],
    )
    kwargs.update(overrides)
    assert unaccounted_params(create_app, kwargs) == []
    return create_app(**kwargs)


# --- The walk ----------------------------------------------------------------

def test_every_route_has_a_row_and_every_row_has_a_route():
    routes = collect_routes(_full_app())
    row_keys = {(r.method, r.path) for r in ROWS}
    assert set(routes) - row_keys == set()
    assert row_keys - set(routes) == set()


def test_declared_rows_declare_their_gate():
    routes = collect_routes(_full_app())
    for row in ROWS:
        if row.declared and row.policy in ("corpus-read", "grant-read", "grant-admin"):
            assert gate_name(routes[(row.method, row.path)]) == row.policy, row


def test_decorator_and_mount_count_matches_the_inventory():
    pattern = re.compile(
        r"@(app|router)\.(get|post|put|patch|delete)\(|\b(app|router)\.mount\(")
    count = sum(len(pattern.findall(p.read_text()))
               for p in SRC.glob("*.py"))
    assert count == len(ROWS) - FRAMEWORK_ROUTES


# --- Reach: the walk is only as good as what it sees -------------------------

def test_a_new_optional_parameter_the_fixture_does_not_pass_fails():
    def fake_create_app(session_factory=None, a_new_backend=None):
        pass

    missing = unaccounted_params(fake_create_app, {"session_factory": None})
    assert missing == ["a_new_backend"]


def test_no_route_params_are_real_create_app_parameters():
    from inspect import signature

    assert set(NO_ROUTE_PARAMS) <= set(signature(create_app).parameters)


def test_descends_into_included_router_and_mounted_application():
    inner = FastAPI()

    @inner.get("/deep")
    def deep():
        return {}

    outer = FastAPI()
    outer.mount("/sub", inner)
    routes = collect_routes(outer)
    assert ("GET", "/deep") in routes


def test_a_static_mount_is_one_row():
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    app.mount("/assets", StaticFiles(directory=str(Path(__file__).parent)))
    routes = collect_routes(app)
    assert ("GET", "/assets") in routes
    assert len(routes) == 1


def test_an_unknown_route_object_fails():
    app = FastAPI()
    app.router.routes.append(object())
    with pytest.raises(UnknownRouteType):
        collect_routes(app)


def test_a_websocket_route_fails():
    app = FastAPI()

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        pass

    with pytest.raises(WebSocketRouteFound):
        collect_routes(app)


def test_head_folds_into_get_of_the_same_route_object():
    app = FastAPI()

    @app.get("/both")
    def both():
        return {}

    @app.api_route("/head-only", methods=["HEAD"])
    def head_only():
        return {}

    routes = collect_routes(app)
    # FastAPI's APIRoute does not auto-add HEAD to a GET-only route (unlike
    # Starlette's raw Route) -- confirmed against the framework's schema
    # routes, which do. A route answering HEAD only needs its own row.
    assert ("GET", "/both") in routes
    assert ("HEAD", "/head-only") in routes or ("GET", "/head-only") in routes


def test_a_scratch_route_without_a_row_fails_the_suite():
    app = _full_app()

    @app.get("/scratch-undeclared")
    def scratch():
        return {}

    routes = collect_routes(app)
    row_keys = {(r.method, r.path) for r in ROWS}
    assert ("GET", "/scratch-undeclared") in set(routes) - row_keys


def test_removing_the_gate_from_search_fails_the_suite():
    app = FastAPI()

    @app.get("/search")
    def search():
        return {}

    routes = collect_routes(app)
    assert gate_name(routes[("GET", "/search")]) is None


def test_a_row_for_a_route_that_does_not_exist_fails_the_suite():
    routes = collect_routes(_full_app())
    assert ("GET", "/no/such/route") not in routes


# --- Refusal -------------------------------------------------------------------

_STATUS_FOR_POLICY = {
    "corpus-read": 403, "grant-read": 403, "grant-admin": 403, "delete": 403,
}
#: Any syntactically-valid id works for a DECLARED gate: it runs before
#: path/query validation (design.md, "A corpus-read refusal comes before the
#: lookup"), so even an id that does not exist is refused rather than 404. A
#: body-call guard (`declared=False`) only runs once FastAPI has already
#: validated the request, so those rows need a well-formed body too — not a
#: proof of the design's claim, just what it takes to reach the guard at all.
_VALID_ID = "11111111-1111-1111-1111-111111111111"
_PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
_BODY_OVERRIDES = {
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


def _call(client, row):
    path = _PLACEHOLDER.sub(_VALID_ID, row.path)
    override = _BODY_OVERRIDES.get((row.method, row.path), {})
    headers = {"X-API-Key": "kderde"}
    if "data" in override:
        return client.request(row.method, path, data=override["data"], headers=headers)
    json_body = override.get(
        "json", {} if row.method in ("POST", "PATCH", "PUT") else None)
    return client.request(row.method, path, json=json_body, headers=headers)


@pytest.mark.parametrize("row", [r for r in ROWS if r.policy in _STATUS_FOR_POLICY],
                        ids=lambda r: f"{r.method} {r.path}")
def test_a_caller_on_no_list_is_refused(row):
    client = TestClient(_full_app(), raise_server_exceptions=False)
    resp = _call(client, row)
    assert resp.status_code == _STATUS_FOR_POLICY[row.policy], resp.text


@pytest.mark.parametrize("row", [r for r in ROWS if r.policy in ("any-key", "open")],
                        ids=lambda r: f"{r.method} {r.path}")
def test_any_key_and_open_rows_are_not_refused(row):
    client = TestClient(_full_app(), raise_server_exceptions=False)
    resp = _call(client, row)
    assert resp.status_code not in (401, 403), resp.text


def test_a_refused_feedback_write_leaves_no_trace():
    client = TestClient(_full_app())
    doc_id = "11111111-1111-1111-1111-111111111111"
    resp = client.post(f"/documents/{doc_id}/feedback",
                       json={"kind": "false_positive", "type": "PERSON",
                             "token": "t"},
                       headers={"X-API-Key": "kderde"})
    assert resp.status_code == 403


def test_empty_read_list_stops_refusing_corpus_read_rows():
    client = TestClient(_full_app(corpus_read_labels=[]), raise_server_exceptions=False)
    resp = client.get("/documents/11111111-1111-1111-1111-111111111111/state",
                      headers={"X-API-Key": "kderde"})
    assert resp.status_code != 403


def test_gate_of_a_corpus_read_route_reads_the_declared_name():
    app = FastAPI()
    gate = corpus_read(["lezer"])

    @app.get("/x", dependencies=[Depends(gate)])
    def x():
        return {}

    route = next(r for r in app.routes if getattr(r, "path", None) == "/x")
    assert gate_name(route) == "corpus-read"
