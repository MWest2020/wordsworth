# SPDX-License-Identifier: MIT
"""`reprocess.one`/`run` log the count-only check after the commit, and only for
a document that was re-anonymised (reanonymise-particle-name-documents).

DB-backed: runs in CI, and locally with WORDSWORTH_TEST_DATABASE_URL.
"""
from __future__ import annotations

import logging

import pytest

from reanon_helpers import (VERBODEN, alleen_voornaam, anonymised_before_the_rule,
                            count_lines, new_key_provider, with_the_rule)
from wordsworth import reprocess
from wordsworth.pipeline import get_anonymized_text, ingest


@pytest.fixture
def logs(caplog):
    caplog.set_level(logging.INFO, logger="wordsworth")
    return caplog


def _row(before, after, added, removed):
    return {"before": before, "after": after, "added": added, "removed": removed}


def test_one_more_name_the_second_time_is_logged_per_type(
        session_factory, mem_store, mem_index, fake_embedder, monkeypatch, logs):
    kp = new_key_provider()
    doc_id = anonymised_before_the_rule(session_factory, mem_store, mem_index,
                                        fake_embedder, kp, monkeypatch)

    outcome, detail, counts = reprocess.one(
        session_factory, doc_id, make_anonymizer=with_the_rule(kp),
        store=mem_store, search_index=mem_index, embedder=fake_embedder)

    assert outcome == "reanonymized" and detail is None
    assert counts == {"PERSON": _row(0, 1, 1, 0), "BSN": _row(1, 1, 0, 0)}
    [line] = count_lines(logs)
    assert line["document_id"] == str(doc_id)
    assert line["counts"] == counts


def test_a_first_name_token_replaced_by_the_whole_name(
        session_factory, mem_store, mem_index, fake_embedder, monkeypatch, logs):
    """Het totaal blijft 1; added 1, removed 1 laat de vervanging zien."""
    kp = new_key_provider()
    doc_id = anonymised_before_the_rule(session_factory, mem_store, mem_index,
                                        fake_embedder, kp, monkeypatch,
                                        detect=alleen_voornaam)
    with session_factory() as s:
        assert "ter Braak" in get_anonymized_text(s, doc_id)  # the miss itself

    _, _, counts = reprocess.one(
        session_factory, doc_id, make_anonymizer=with_the_rule(kp),
        store=mem_store, search_index=mem_index, embedder=fake_embedder)

    assert counts["PERSON"] == _row(1, 1, 1, 1)
    with session_factory() as s:
        assert "Braak" not in get_anonymized_text(s, doc_id)
    [line] = count_lines(logs)
    assert line["counts"]["PERSON"] == _row(1, 1, 1, 1)


def test_a_failed_commit_logs_no_counts(
        session_factory, mem_store, mem_index, fake_embedder, monkeypatch, logs):
    kp = new_key_provider()
    doc_id = anonymised_before_the_rule(session_factory, mem_store, mem_index,
                                        fake_embedder, kp, monkeypatch)
    with session_factory() as s:
        before = get_anonymized_text(s, doc_id)

    class CommitWeigert(RuntimeError):
        pass

    def weigert():
        raise CommitWeigert()

    def kapotte_factory():
        s = session_factory()
        s.commit = weigert
        return s

    entity_counts: dict = {}
    counts, problems = reprocess.run(
        kapotte_factory, [doc_id], make_anonymizer=with_the_rule(kp),
        store=mem_store, search_index=mem_index, embedder=fake_embedder,
        entity_counts=entity_counts)

    assert counts["failed"] == 1
    assert problems == {str(doc_id): "CommitWeigert"}
    assert entity_counts == {}
    assert count_lines(logs) == []
    with session_factory() as s:
        assert get_anonymized_text(s, doc_id) == before   # nothing committed


def test_a_failing_detail_query_logs_no_counts(
        session_factory, mem_store, mem_index, fake_embedder, monkeypatch, logs):
    """The count line comes after the `value-not-located` read too: a document
    is never both logged as re-anonymised and reported as failed."""
    kp = new_key_provider()
    doc_id = anonymised_before_the_rule(session_factory, mem_store, mem_index,
                                        fake_embedder, kp, monkeypatch)

    class DetailWeigert(RuntimeError):
        pass

    def weigert(_session, _document_id):
        raise DetailWeigert()

    monkeypatch.setattr(reprocess, "_value_not_located_detail", weigert)
    entity_counts: dict = {}
    counts, problems = reprocess.run(
        session_factory, [doc_id], make_anonymizer=with_the_rule(kp),
        store=mem_store, search_index=mem_index, embedder=fake_embedder,
        entity_counts=entity_counts)

    assert counts["failed"] == 1
    assert problems == {str(doc_id): "DetailWeigert"}
    assert entity_counts == {}
    assert count_lines(logs) == []


def test_skipped_and_failed_documents_log_no_counts_and_keep_their_outcome(
        session_factory, mem_store, mem_index, fake_embedder, monkeypatch, logs):
    kp = new_key_provider()
    doc_id = anonymised_before_the_rule(session_factory, mem_store, mem_index,
                                        fake_embedder, kp, monkeypatch)
    with session_factory() as s:          # REGISTERED, never processed: skipped
        skipped_id = ingest(s, mem_store, b"%PDF-1.4 niet verwerkt").id
        s.commit()

    class Weigert:
        def anonymize(self, text):
            raise RuntimeError(f"de motor stikte in {text}")

    entity_counts: dict = {}
    counts, problems = reprocess.run(
        session_factory, [skipped_id, doc_id],
        make_anonymizer=lambda s, domain: Weigert(),
        store=mem_store, search_index=mem_index, embedder=fake_embedder,
        entity_counts=entity_counts)

    assert counts == {"reanonymized": 0, "skipped": 1, "retryable": 0, "failed": 1}
    assert problems == {str(doc_id): "RuntimeError"}
    assert entity_counts == {}
    assert count_lines(logs) == []


def test_run_still_returns_counts_and_problems(
        session_factory, mem_store, mem_index, fake_embedder, monkeypatch, logs):
    """Een aanroeper die geen `entity_counts` meegeeft merkt niets."""
    kp = new_key_provider()
    doc_id = anonymised_before_the_rule(session_factory, mem_store, mem_index,
                                        fake_embedder, kp, monkeypatch)
    uit = reprocess.run(session_factory, [doc_id], make_anonymizer=with_the_rule(kp),
                        store=mem_store, search_index=mem_index,
                        embedder=fake_embedder)
    assert isinstance(uit, tuple) and len(uit) == 2
    assert uit[0]["reanonymized"] == 1 and uit[1] == {}
    assert len(count_lines(logs)) == 1      # logged even without a collector


def test_the_log_holds_no_value_token_text_or_offset(
        session_factory, mem_store, mem_index, fake_embedder, monkeypatch, logs):
    kp = new_key_provider()
    doc_id = anonymised_before_the_rule(session_factory, mem_store, mem_index,
                                        fake_embedder, kp, monkeypatch,
                                        detect=alleen_voornaam)
    reprocess.one(session_factory, doc_id, make_anonymizer=with_the_rule(kp),
                  store=mem_store, search_index=mem_index, embedder=fake_embedder)

    for verboden in VERBODEN:
        assert verboden not in logs.text, verboden
    [line] = count_lines(logs)
    assert set(line) == {"event", "document_id", "counts", "level"}
    for per_type in line["counts"].values():
        assert set(per_type) == {"before", "after", "added", "removed"}
        assert all(isinstance(v, int) for v in per_type.values())
