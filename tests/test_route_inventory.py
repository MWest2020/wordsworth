# SPDX-License-Identifier: MIT
"""The walk (api-corpus-read-gate, task 3): every route the application mounts
has a row, every row has a route, every declared gate is declared, and the
walk sees everything. Each reach test makes a scratch change to the real
application and runs the same check the walk test runs, so it shows that
check failing on the change."""
from __future__ import annotations

import shutil
from inspect import Parameter, signature
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.websockets import WebSocket
from starlette.routing import Route
from starlette.staticfiles import StaticFiles

from inventory_app import full_app, ungated_ingest_app, ungated_search_app
from route_inventory import (ROWS, AnyMethodRoute, Row, UnknownRouteType,
                             UnmountedParameter, WebSocketRouteFound,
                             collect_routes, count_registrations, missing_rows,
                             orphan_rows, registration_mismatch,
                             undeclared_gates, ungated_writes)
from wordsworth.api import create_app

SRC = Path(__file__).parent.parent / "src" / "wordsworth"


def test_the_walk_on_the_real_application():
    routes = collect_routes(full_app())
    assert missing_rows(routes) == set()
    assert orphan_rows(routes) == set()
    assert undeclared_gates(routes) == set()
    assert ungated_writes(routes) == set()
    assert registration_mismatch(count_registrations(SRC)) == 0


def test_no_route_params_are_real_create_app_parameters():
    from route_inventory import NO_ROUTE_PARAMS
    assert set(NO_ROUTE_PARAMS) <= set(signature(create_app).parameters)


# (a) a new optional create_app parameter the fixture does not pass
def test_a_new_create_app_parameter_fails():
    def scratch_create_app(*, a_new_backend=None, **kwargs):
        return create_app(**kwargs)

    params = list(signature(create_app).parameters.values())
    scratch_create_app.__signature__ = signature(create_app).replace(parameters=[
        *params, Parameter("a_new_backend", Parameter.KEYWORD_ONLY, default=None)])
    with pytest.raises(UnmountedParameter, match="a_new_backend"):
        full_app(factory=scratch_create_app)


# (b) a registration in src/, also in a subpackage, without a row
@pytest.mark.parametrize("where", [
    "api.py", "eval/scratch.py"], ids=["module", "subpackage"])
@pytest.mark.parametrize("line", [
    '@app.api_route("/scratch", methods=["GET"])',
    'app.add_api_route("/scratch", f)', 'app.add_route("/scratch", f)',
    '@router.websocket("/scratch")', 'app.mount("/scratch", other)'])
def test_a_registration_without_a_row_fails_the_count(tmp_path, where, line):
    copy = tmp_path / "wordsworth"
    shutil.copytree(SRC, copy, ignore=shutil.ignore_patterns("__pycache__"))
    target = copy / where
    target.write_text((target.read_text() if target.exists() else "") + f"\n{line}\n")
    assert registration_mismatch(count_registrations(copy)) == 1


# (c) a route on a second included router, and inside a mounted application
def test_a_second_router_and_a_mounted_app_are_walked_with_their_prefix():
    app = full_app()
    second = APIRouter(prefix="/second")

    @second.get("/x")
    def x():
        return {}

    inner = FastAPI(openapi_url=None)

    @inner.get("/deep")
    def deep():
        return {}

    app.include_router(second, prefix="/v2")
    app.mount("/sub", inner)
    assert missing_rows(collect_routes(app)) == {("GET", "/v2/second/x"),
                                                ("GET", "/sub/deep")}


# (d) an object of an unknown type, at the top and inside an included router
def test_an_unknown_route_object_fails():
    app = full_app()
    app.router.routes.append(object())
    with pytest.raises(UnknownRouteType):
        collect_routes(app)


def test_an_unknown_route_object_inside_the_console_router_fails():
    app = full_app()
    console = next(r for r in app.routes if hasattr(r, "original_router"))
    console.original_router.routes.append(object())
    with pytest.raises(UnknownRouteType):
        collect_routes(app)


def test_a_route_answering_every_method_fails():
    class RawAsgi:   # an ASGI app, not a function: Starlette sets methods=None
        async def __call__(self, scope, receive, send):
            pass

    app = full_app()
    app.router.routes.append(Route("/raw", endpoint=RawAsgi()))
    with pytest.raises(AnyMethodRoute):
        collect_routes(app)


# (e) a WebSocketRoute: the auth middleware passes non-HTTP scopes through
def test_a_websocket_route_fails():
    app = full_app()

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        pass

    with pytest.raises(WebSocketRouteFound):
        collect_routes(app)


# (f) a scratch route without a row; the gate off /search; a row without a route
def test_a_scratch_route_without_a_row_fails():
    app = full_app()

    @app.get("/scratch-undeclared")
    def scratch():
        return {}

    assert missing_rows(collect_routes(app)) == {("GET", "/scratch-undeclared")}


def test_removing_the_gate_from_search_fails():
    assert undeclared_gates(collect_routes(ungated_search_app())) == {
        ("GET", "/search")}


def test_a_row_for_a_route_that_does_not_exist_fails():
    rows = ROWS + [Row("GET", "/no/such/route", "corpus-read", "scratch")]
    assert orphan_rows(collect_routes(full_app()), rows) == {("GET", "/no/such/route")}


def test_a_static_mount_is_one_row_with_its_prefix():
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    sub = FastAPI(openapi_url=None)
    sub.mount("/assets", StaticFiles(directory=str(Path(__file__).parent)))
    app.mount("/outer", sub)
    assert set(collect_routes(app)) == {("GET", "/outer/assets")}


def test_head_folds_into_get_and_a_head_only_route_has_its_own_row():
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

    async def both(request):
        pass

    app.router.routes.append(Route("/both", endpoint=both))   # GET + HEAD

    @app.api_route("/head-only", methods=["HEAD"])
    def head_only():
        return {}

    assert set(collect_routes(app)) == {("GET", "/both"), ("HEAD", "/head-only")}


# (g) ingest-requires-corpus-read (#526): a writing route no check refuses
def test_removing_the_gate_from_ingest_fails():
    assert undeclared_gates(collect_routes(ungated_ingest_app())) == {
        ("POST", "/ingest")}


@pytest.mark.parametrize("policy", ["any-key", "open", "grant"])
def test_a_write_route_recorded_as_unrefused_fails(policy):
    rows = [r for r in ROWS if r.path != "/ingest"] + [
        Row("POST", "/ingest", policy, "scratch")]
    assert ungated_writes(collect_routes(full_app()), rows) == {("POST", "/ingest")}


def test_a_new_write_route_cannot_pass_as_any_key():
    app = full_app()

    @app.delete("/scratch-write")
    def scratch():
        return {}

    rows = ROWS + [Row("DELETE", "/scratch-write", "any-key", "scratch")]
    assert ungated_writes(collect_routes(app), rows) == {("DELETE", "/scratch-write")}


def test_grant_rows_are_exactly_the_two_reveal_routes():
    from route_inventory import GRANT_DECIDED
    assert {(r.method, r.path) for r in ROWS if r.policy == "grant"} == GRANT_DECIDED
