# SPDX-License-Identifier: MIT
"""`POST /reprocess` returns the count-only check per re-anonymised document in
`entity_counts` (reanonymise-particle-name-documents).

DB-backed: runs in CI, and locally with WORDSWORTH_TEST_DATABASE_URL.
"""
from __future__ import annotations

import json
import logging
import re

from fastapi.testclient import TestClient

from reanon_helpers import (VERBODEN, alleen_voornaam, anonymised_before_the_rule,
                            count_lines, new_key_provider, niets)
from wordsworth.api import create_app
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.pipeline import ingest
from wordsworth.pseudonymizer import ReversibleAnonymizer


def test_the_answer_holds_counts_for_the_reanonymised_document_only(
        session_factory, mem_store, mem_index, fake_embedder, monkeypatch, caplog):
    caplog.set_level(logging.INFO, logger="wordsworth")
    kp = new_key_provider()
    doc_id = anonymised_before_the_rule(session_factory, mem_store, mem_index,
                                        fake_embedder, kp, monkeypatch,
                                        detect=alleen_voornaam)
    with session_factory() as s:          # REGISTERED, never processed: skipped
        skipped_id = ingest(s, mem_store, b"%PDF-1.4 niet verwerkt").id
        s.commit()

    app = create_app(
        session_factory=session_factory, store=mem_store, search_index=mem_index,
        embedder=fake_embedder, rate_limiters={},
        anonymizer_factory=lambda s: ReversibleAnonymizer(
            kp, PostgresMappingStore(s), detect=niets))
    res = TestClient(app).post(
        "/reprocess", json={"document_ids": [str(doc_id), str(skipped_id)]})
    assert res.status_code == 200
    uit = res.json()

    assert uit["reanonymized"] == 1 and uit["skipped"] == 1
    assert uit["entity_counts"] == {str(doc_id): {
        "BSN": {"before": 1, "after": 1, "added": 0, "removed": 0},
        "PERSON": {"before": 1, "after": 1, "added": 1, "removed": 1},
    }}
    assert str(skipped_id) not in uit["entity_counts"]

    # The answer and the logs: ids, type names and numbers -- no token, no value.
    tekst = json.dumps(uit)
    assert not re.search(r"\[[A-Z0-9_]+:[0-9a-f]{8}\]", tekst)
    for verboden in VERBODEN:
        assert verboden not in tekst, verboden
        assert verboden not in caplog.text, verboden
    [line] = count_lines(caplog)
    assert line["document_id"] == str(doc_id)
    assert line["counts"] == uit["entity_counts"][str(doc_id)]
