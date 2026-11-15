# SPDX-License-Identifier: MIT
"""A refused write leaves nothing (api-corpus-read-gate, tasks 1 and 2).

Every refusal is made on a seeded corpus in a real Postgres, and afterwards
every table holds as many rows as before, topic names and declared
combinations unchanged: no audit record, no document row, no mapping row, no
feedback, no rename, no declaration. DB-backed: skips without a Postgres.
"""
from __future__ import annotations

import re

import pytest

from read_gate_world import (DECLARED, KEY_OF, SEEDED_NAME, UNKNOWN_ID,
                             make_world, request_for, send)

CORPUS_READ = {"detail": "caller not authorized for corpus read"}


@pytest.fixture(scope="module")
def world(database_url):
    return make_world(database_url)


@pytest.fixture(scope="module")
def client(world):
    return world.client()


REFUSED_WRITES = [
    ("POST", "/documents/{document_id}/feedback"),
    ("POST", "/dossiers/{dossier_id}/topics"),
    ("PATCH", "/topics/{topic_id}"),
    ("POST", "/topics/{topic_id}/label"),
    ("POST", "/dossiers/{dossier_id}/summaries"),
    ("POST", "/reprocess"),
    ("POST", "/console/topics"),
    ("POST", "/console/topics/{topic_id}/label"),
    ("POST", "/console/combinations"),
]


@pytest.mark.parametrize("method,path", REFUSED_WRITES)
def test_a_refused_write_writes_nothing(world, client, method, path):
    before = world.snapshot()
    resp = send(client, world, method, path, "derde")
    assert resp.status_code == 403, resp.text
    assert world.snapshot() == before


def _as_derde(client, method, url, **kw):
    return client.request(method, url, headers={"X-API-Key": KEY_OF["derde"]}, **kw)


@pytest.mark.parametrize("body", [
    None, {"document_ids": "REAL"}, {"document_ids": [UNKNOWN_ID]},
], ids=["no body", "real ids", "unknown id"])
def test_reprocess_refuses_the_same_way_and_reprocesses_nothing(world, client, body):
    if body and body["document_ids"] == "REAL":
        body = {"document_ids": [world.doc_id]}
    before = world.snapshot()
    resp = _as_derde(client, "POST", "/reprocess", json=body)
    assert (resp.status_code, resp.json()) == (403, CORPUS_READ)
    assert world.snapshot() == before


@pytest.mark.parametrize("doc", ["REAL", UNKNOWN_ID])
def test_feedback_is_refused_for_an_existing_and_an_unknown_document(world, client, doc):
    doc = world.doc_id if doc == "REAL" else doc
    before = world.snapshot()
    resp = _as_derde(client, "POST", f"/documents/{doc}/feedback",
                     json={"kind": "fn", "type": "PERSON"})
    assert (resp.status_code, resp.json()) == (403, CORPUS_READ)
    assert world.snapshot() == before


@pytest.mark.parametrize("method,path", [
    ("POST", "/documents/{id}/feedback"), ("PATCH", "/topics/{id}"),
    ("POST", "/reprocess")])
def test_a_body_that_is_not_json_is_422_for_anyone_and_changes_nothing(
        world, client, method, path):
    """FastAPI parses a JSON body before it resolves dependencies (design.md):
    the 422 says nothing about the corpus, so it is the same for an existing and
    an unknown id."""
    real = world.doc_id if "feedback" in path else world.topic_id()
    before = world.snapshot()
    headers = {"Content-Type": "application/json", "X-API-Key": KEY_OF["derde"]}
    answers = [client.request(method, path.replace("{id}", i), content=b"{nope",
                              headers=headers)
               for i in (real, UNKNOWN_ID)]
    assert {a.status_code for a in answers} == {422}
    assert answers[0].json() == answers[1].json()
    assert world.snapshot() == before


@pytest.mark.parametrize("label", ["derde", "lezer"])
def test_a_dataset_run_is_refused_to_a_non_issuer_and_writes_nothing(
        world, client, label):
    before = world.snapshot()
    resp = send(client, world, "POST", "/datasets/pseudonymize", label)
    assert resp.status_code == 403
    assert resp.json() == {"detail": "caller not authorized to issue or revoke grants"}
    assert "csv" not in resp.text and "[PERSON" not in resp.text
    # documents (no dataset row), audit_records (no dataset_pseudonymize),
    # pii_mappings and document_pseudonyms (no mapping) all unchanged:
    assert world.snapshot() == before


def test_an_issuer_runs_a_dataset_as_before(world, client):
    before = world.snapshot()
    resp = send(client, world, "POST", "/datasets/pseudonymize", "uitgever")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rows"] == 1 and SEEDED_NAME not in body["csv"]
    after = world.snapshot()
    # the dataset artefact's row, its registration and its run record
    assert after["documents"] == before["documents"] + 1
    assert after["audit_records"] == before["audit_records"] + 2


def test_combinations_are_refused_to_derde_and_lezers_declaration_stays(world, client):
    before = world.snapshot()
    assert _as_derde(client, "GET", "/console/combinations").status_code == 403
    url, spec = request_for(world, "POST", "/console/combinations")
    assert _as_derde(client, "POST", url, **spec).status_code == 403
    after = world.snapshot()
    assert after == before
    assert tuple(after["declared"][0]) == DECLARED     # reason and declared_by kept


def test_a_reader_declares_a_combination_and_sees_its_reach(world, client):
    headers = {"X-API-Key": KEY_OF["lezer"]}
    resp = client.post("/console/combinations", headers=headers,
                       data={"types": "PERSON POSTCODE", "reason": "lezer verklaart"})
    assert resp.status_code == 303
    rows = [tuple(r) for r in world.snapshot()["declared"]]
    assert ("PERSON+POSTCODE", "lezer verklaart", "lezer") in rows
    page = client.get("/console/combinations", headers=headers)
    assert page.status_code == 200 and "lezer verklaart" in page.text
    assert re.search(r'<span class="state">\d+</span>', page.text)   # its reach
