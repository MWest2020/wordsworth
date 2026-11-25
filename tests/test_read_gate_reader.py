# SPDX-License-Identifier: MIT
"""Nobody who could read before is locked out (api-corpus-read-gate, task 3).

Reader parity: every corpus-read and grant-read row, requested as ``lezer`` on
a seeded corpus, answers what it answers on main. Scope off: every row, as
``derde`` with an empty read list, answers what it answers on main. That is
the demo lockout guard: a gate that refused a reader would show up here, not
in production.

``MAIN`` was measured on origin/main 07cf9d9 with this module's own requests
(tests/read_gate_world.py), both as ``lezer`` and as ``derde`` with the scope
off; the two tables were identical. DB-backed: skips without a Postgres.
"""
from __future__ import annotations

import pytest

from read_gate_world import make_world, send
from route_rows import ROWS

#: Status on main; every row not named here answered 200.
MAIN = {
    ("POST", "/documents/{document_id}/feedback"): 201,
    ("GET", "/roles"): 403, ("POST", "/roles"): 403,
    ("PUT", "/roles/{name}/types"): 403, ("POST", "/roles/{name}/deactivate"): 403,
    ("POST", "/roles/{name}/activate"): 403, ("POST", "/grants"): 403,
    ("POST", "/grants/{grant_id}/revoke"): 403,
    ("GET", "/group-roles"): 403, ("PUT", "/group-roles/{group}/{role}"): 403,
    ("DELETE", "/group-roles/{group}/{role}"): 403,
    ("DELETE", "/documents/{document_id}"): 403,
    ("DELETE", "/dossiers/{dossier_id}"): 403,
    ("POST", "/documents/{document_id}/reveal"): 422,      # no grant in the body
    ("POST", "/documents/{document_id}/reveal.pdf"): 422,
    ("POST", "/ingest"): 422,                               # no file
    ("GET", "/console"): 303, ("POST", "/console/combinations"): 303,
    ("GET", "/console/roles"): 403, ("POST", "/console/roles"): 403,
    ("POST", "/console/roles/switch"): 403,
    ("POST", "/console/group-roles"): 403, ("POST", "/console/group-roles/delete"): 403,
    ("POST", "/console/login"): 422, ("GET", "/console/static"): 307,
    ("GET", "/console/logout"): 303,
}
#: Where this change answers differently from main, on purpose: a dataset run
#: is a token lookup and takes the grant-issue right, whatever the read list
#: says (design.md, "POST /datasets/pseudonymize"; Mark's default 6, #447).
NARROWED = {("POST", "/datasets/pseudonymize"): 403}


def main_status(row) -> int:
    return MAIN.get((row.method, row.path), 200)


@pytest.fixture(scope="module")
def world(database_url):
    return make_world(database_url)


@pytest.fixture(scope="module")
def reader_client(world):
    return world.client()


@pytest.fixture(scope="module")
def scope_off_client(world):
    return world.client(corpus_read_labels=[])


READ_ROWS = [r for r in ROWS if r.policy in ("corpus-read", "grant-read")]


def test_there_are_28_reader_rows():
    assert len(READ_ROWS) == 28


@pytest.mark.parametrize("row", READ_ROWS, ids=lambda r: f"{r.method} {r.path}")
def test_a_reader_answers_as_on_main(world, reader_client, row):
    resp = send(reader_client, world, row.method, row.path, "lezer")
    assert resp.status_code == main_status(row), resp.text[:300]


@pytest.mark.parametrize("row", ROWS, ids=lambda r: f"{r.method} {r.path}")
def test_with_the_scope_off_a_caller_on_no_list_answers_as_on_main(
        world, scope_off_client, row):
    expected = NARROWED.get((row.method, row.path), main_status(row))
    resp = send(scope_off_client, world, row.method, row.path, "derde")
    assert resp.status_code == expected, resp.text[:300]
