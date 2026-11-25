# SPDX-License-Identifier: MIT
"""#469: a document deleted while `reprocess.one` waits for its row is
reported `skipped`, not `reanonymized`; the state found goes to the log.

`reprocess.one` reads the state without a lock and then calls `reanonymize`,
which locks the row (#463). A deletion in flight commits first; `reanonymize`
then reads `deleted` and writes nothing -- and the run used to count the
document as reanonymized all the same."""
from __future__ import annotations

import json
import logging
import threading

from sqlalchemy import select, text

from race_setup import run, wait_for_a_lock_waiter
from test_reanonymize_delete_race import _HoldingStore, _indexed
from wordsworth import reprocess
from wordsworth.anonymizer import DeterministicAnonymizer
from wordsworth.audit import current_state
from wordsworth.deletion import delete_document
from wordsworth.models import AuditRecord
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State


def _skip_lines(caplog) -> list[dict]:
    lines = []
    for rec in caplog.records:
        try:
            parsed = json.loads(rec.getMessage())
        except ValueError:
            continue
        if isinstance(parsed, dict) and parsed.get("event") == "reprocess_skipped":
            lines.append(parsed)
    return lines


def _one(session_factory, doc_id, store, index, embedder):
    return reprocess.one(session_factory, doc_id,
                         make_anonymizer=lambda s, domain: DeterministicAnonymizer(),
                         store=store, search_index=index, embedder=embedder)


def test_a_document_deleted_mid_run_is_skipped_not_reanonymized(
        session_factory, born_digital_pii_pdf, fake_embedder, caplog):
    caplog.set_level(logging.INFO, logger="wordsworth.pipeline")
    store, index = _HoldingStore(), InMemoryIndex()
    doc_id = _indexed(session_factory, store, index, born_digital_pii_pdf,
                      fake_embedder)
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()

    def hold():
        paused.set()
        assert resume.wait(30), "never resumed"

    def deleting():
        with session_factory() as s:
            s.execute(text("SET lock_timeout = '20s'"))
            store.on_delete = hold  # row held, nothing committed: still `indexed`
            delete_document(s, doc_id, store, index, actor="t")
            s.commit()

    def reprocessing():
        result["one"] = _one(session_factory, doc_id, store, index, fake_embedder)

    dele = run(errors, "delete", deleting)
    assert paused.wait(10)
    repr_ = run(errors, "reprocess", reprocessing)
    try:
        wait_for_a_lock_waiter(session_factory)  # past its own state check
    finally:
        resume.set()
        dele.join(30)
        repr_.join(30)

    assert not errors, errors
    assert result["one"] == ("skipped", None, None)
    assert _skip_lines(caplog) == [{"event": "reprocess_skipped", "level": "info",
                                    "document_id": str(doc_id), "state": "deleted"}]
    with session_factory() as s:
        assert current_state(s, doc_id) == State.DELETED
        steps = s.execute(select(AuditRecord.step).where(
            AuditRecord.document_id == doc_id)).scalars().all()
        assert "reanonymize" not in steps


def test_run_counts_it_as_skipped_and_names_the_reason(
        session_factory, born_digital_pii_pdf, fake_embedder, monkeypatch):
    """The same through `run`: one skipped, none reanonymized, and nothing in
    `problems`, which holds failures only."""
    store, index = _HoldingStore(), InMemoryIndex()
    doc_id = _indexed(session_factory, store, index, born_digital_pii_pdf,
                      fake_embedder)
    real = reprocess.reanonymize

    def deleted_first(session, document_id, *args, **kwargs):
        # A deletion that commits between `one`'s state check and the lock.
        with session_factory() as s:
            delete_document(s, document_id, store, index, actor="t")
            s.commit()
        return real(session, document_id, *args, **kwargs)
    monkeypatch.setattr(reprocess, "reanonymize", deleted_first)

    per_type: dict = {}
    counts, problems = reprocess.run(
        session_factory, [doc_id],
        make_anonymizer=lambda s, domain: DeterministicAnonymizer(),
        store=store, search_index=index, embedder=fake_embedder,
        entity_counts=per_type)
    assert counts == {"reanonymized": 0, "skipped": 1, "retryable": 0, "failed": 0}
    assert problems == {}
    assert per_type == {}


def test_a_document_that_is_simply_not_indexed_is_skipped_without_a_log_line(
        session_factory, born_digital_pdf, fake_embedder, caplog):
    """Unchanged: a state `one` reads itself is not a race to report."""
    caplog.set_level(logging.INFO, logger="wordsworth.pipeline")
    from wordsworth.pipeline import ingest
    store, index = _HoldingStore(), InMemoryIndex()
    with session_factory() as s:
        doc_id = ingest(s, store, born_digital_pdf).id
        s.commit()
    assert _one(session_factory, doc_id, store, index, fake_embedder) == (
        "skipped", None, None)
    assert _skip_lines(caplog) == []
