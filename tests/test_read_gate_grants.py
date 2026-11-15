# SPDX-License-Identifier: MIT
"""``GET /grants/{id}`` (grant-read) on a seeded corpus, and the startup
warning for an empty read list (api-corpus-read-gate, tasks 2 and 4)."""
from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from inventory_app import call, full_app
from read_gate_world import KEY_OF, UNKNOWN_ID, make_world
from route_rows import ROWS


@pytest.fixture(scope="module")
def world(database_url):
    return make_world(database_url)


def _get(world, client, grant_id, label):
    return client.get(f"/grants/{grant_id}", headers={"X-API-Key": KEY_OF[label]})


@pytest.mark.parametrize("label", ["lezer", "uitgever"])
def test_a_reader_and_an_issuer_read_a_grant(world, label):
    resp = _get(world, world.client(), world.grant_id, label)
    assert resp.status_code == 200, resp.text
    assert resp.json()["grant_id"] == world.grant_id


@pytest.mark.parametrize("label", ["lezer", "uitgever"])
def test_an_unknown_grant_is_404_for_who_may_read_one(world, label):
    assert _get(world, world.client(), "g-" + UNKNOWN_ID, label).status_code == 404


def test_derde_gets_the_same_403_for_an_existing_and_an_unknown_grant(world):
    client = world.client()
    answers = [_get(world, client, g, "derde") for g in (world.grant_id, UNKNOWN_ID)]
    assert [a.status_code for a in answers] == [403, 403]
    assert answers[0].json() == answers[1].json()


# --- The startup warning -----------------------------------------------------

def _warnings(caplog) -> list[dict]:
    out = []
    for rec in caplog.records:
        try:
            line = json.loads(rec.getMessage())
        except ValueError:
            continue
        if line.get("event") == "empty_corpus_read_scope":
            assert rec.levelno == logging.WARNING
            out.append(line)
    return out


NO_GRANTS = dict(grant_store=None, grant_store_factory=None)


@pytest.mark.parametrize("overrides,warned", [
    (dict(corpus_read_labels=[]), 1),                          # auth + grants, empty
    (dict(corpus_read_labels=["lezer"]), 0),                   # a list
    (dict(corpus_read_labels=[], api_keys={}), 0),             # no authentication
    (dict(corpus_read_labels=[], **NO_GRANTS), 0),             # no grant store
], ids=["warned once", "with a list", "without auth", "without grant store"])
def test_the_empty_read_list_warning(caplog, overrides, warned):
    caplog.set_level(logging.WARNING, logger="wordsworth.pipeline")
    full_app(**overrides)
    assert len(_warnings(caplog)) == warned


def test_the_warning_changes_no_answer(caplog):
    """The warned configuration answers like the scope off it is: no corpus-read
    row refuses a caller on no list. (The DB-backed scope-off test in
    test_read_gate_reader.py runs every row in this configuration.)"""
    caplog.set_level(logging.WARNING, logger="wordsworth.pipeline")
    client = TestClient(full_app(corpus_read_labels=[]), raise_server_exceptions=False)
    assert len(_warnings(caplog)) == 1
    for row in ROWS:
        if row.policy in ("corpus-read", "grant-read"):
            assert call(client, row).status_code != 403, row
