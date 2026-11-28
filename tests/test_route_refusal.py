# SPDX-License-Identifier: MIT
"""The refusal test (api-corpus-read-gate, tasks 1 and 3): every row requested
as a caller on no list answers what its policy promises, and a declared gate
refuses before validation and before the route's own lookup. No database: the
gate answers first. ``test_read_gate_reader.py`` runs the rows on a seeded
corpus, as a reader and with the scope off."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from inventory_app import (VALID_ID, call, full_app, ungated_ingest_app,
                           ungated_search_app)
from route_inventory import ROWS, collect_routes

REFUSED = ("corpus-read", "grant-read", "grant-admin", "delete")
_ROUTES = collect_routes(full_app())


def _answers_head(row) -> bool:
    route = _ROUTES[(row.method, row.path)].route
    return row.method == "GET" and "HEAD" in (getattr(route, "methods", None) or ())


@pytest.fixture(scope="module")
def client():
    return TestClient(full_app(), raise_server_exceptions=False)


@pytest.mark.parametrize("row", [r for r in ROWS if r.policy in REFUSED],
                         ids=lambda r: f"{r.method} {r.path}")
def test_a_caller_on_no_list_is_refused(client, row):
    resp = call(client, row)
    assert resp.status_code == 403, resp.text
    if _answers_head(row):
        assert call(client, row, method="HEAD").status_code == 403


@pytest.mark.parametrize("row", [r for r in ROWS if r.policy not in REFUSED + ("grant",)],
                         ids=lambda r: f"{r.method} {r.path}")
def test_any_key_and_open_rows_are_not_refused(client, row):
    resp = call(client, row)
    assert resp.status_code not in (401, 403), resp.text
    if _answers_head(row):
        assert call(client, row, method="HEAD").status_code not in (401, 403)


def test_the_refusal_suite_fails_when_search_loses_its_gate():
    """The scratch change of task 3(f), seen by the refusal test too."""
    client = TestClient(ungated_search_app(), raise_server_exceptions=False)
    row = next(r for r in ROWS if r.path == "/search")
    assert call(client, row).status_code != 403


def test_the_refusal_suite_fails_when_ingest_loses_its_gate():
    """#526: on main `POST /ingest` reached validation for a caller on no list."""
    client = TestClient(ungated_ingest_app(), raise_server_exceptions=False)
    row = next(r for r in ROWS if r.path == "/ingest")
    assert call(client, row).status_code == 422


_SEARCH = "caller not authorized for corpus read"


@pytest.mark.parametrize("path", [
    "/search",                                   # q missing
    "/search?q=x&size=notanumber",               # q present, size malformed
    "/documents/not-a-uuid/state",               # malformed path id
    f"/documents/{VALID_ID}/state",              # well formed, unknown
    f"/documents/{VALID_ID}",
    "/export/ranking.csv",                       # query missing
])
def test_the_refusal_comes_before_validation_and_lookup(client, path):
    resp = client.get(path, headers={"X-API-Key": "kderde"})
    assert resp.status_code == 403
    assert resp.json() == {"detail": _SEARCH}


def test_a_grant_read_refusal_is_the_same_for_a_malformed_id(client):
    for gid in ("x", VALID_ID, "g-" + "0" * 40):
        resp = client.get(f"/grants/{gid}", headers={"X-API-Key": "kderde"})
        assert resp.status_code == 403
        assert resp.json() == {"detail": "caller not authorized to read this grant"}


def test_a_read_list_with_auth_off_refuses_every_corpus_read_route():
    """No keys, no identity: there is no caller to admit, so a set read list
    refuses everybody. `GET /grants/{id}` stays reachable: without auth the
    issuer check admits everyone, as it always has (docs/how-to/api-auth.md)."""
    app = full_app(api_keys={}, corpus_read_labels=["lezer"])
    client = TestClient(app, raise_server_exceptions=False)
    routes = collect_routes(app)
    rows = [r for r in ROWS if (r.method, r.path) in routes]
    assert not any(r.path.startswith("/console/") and r.path != "/console/static"
                   for r in rows)           # the console is not mounted
    for row in rows:
        resp = call(client, row, key=None)
        if row.policy == "corpus-read":
            assert resp.status_code == 403, row
        elif row.policy == "grant-read":
            assert resp.status_code != 403, row
