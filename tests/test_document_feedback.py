# SPDX-License-Identifier: MIT
"""POST /documents/{id}/feedback refuses a deleted document
(deleted-document-answers-410, design.md decision 5, tasks 2.2 and 2.3).

A deletion is terminal: feedback on a deleted document is refused and writes
nothing, also when the deletion lands while the feedback request is running.
The route decides under the chain lock `audit.append` takes (`lock_chain`,
taken first): either the feedback record precedes the `deleted` record, or
the request answers 410 and writes nothing -- never the other way round.
DB-backed: skips without a Postgres, like the other integration tests.
"""
from __future__ import annotations

import threading

from fastapi.testclient import TestClient
from sqlalchemy import select

from race_setup import run, wait_for_a_lock_waiter
from wordsworth import audit
from wordsworth.api import create_app
from wordsworth.audit import current_state, verify_chain
from wordsworth.deletion import delete_document
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord
from wordsworth.pipeline import ingest, process
from wordsworth.pseudonymizer import Pseudonymizer
from wordsworth.states import State


def _prepare(session_factory, mem_store, mem_index, fake_embedder, pdf):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder)
        s.commit()
        return doc.id


def _client(session_factory):
    return TestClient(create_app(session_factory=session_factory))


def _records(session_factory, doc_id):
    with session_factory() as s:
        return s.execute(
            select(AuditRecord).where(AuditRecord.document_id == doc_id)
            .order_by(AuditRecord.seq)).scalars().all()


def test_feedback_after_the_deletion_is_410_and_writes_nothing(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                      born_digital_pii_pdf)
    with session_factory() as s:
        delete_document(s, doc_id, mem_store, mem_index, actor="t")
        s.commit()
    before = _records(session_factory, doc_id)

    r = _client(session_factory).post(f"/documents/{doc_id}/feedback",
                                      json={"kind": "fn", "type": "PERSON"})
    assert r.status_code == 410
    assert r.json() == {"detail": "document deleted"}

    after = _records(session_factory, doc_id)
    assert len(after) == len(before)
    with session_factory() as s:
        assert verify_chain(s) == (True, None)


def test_earlier_feedback_is_kept(session_factory, mem_store, mem_index,
                                  fake_embedder, born_digital_pii_pdf):
    doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                      born_digital_pii_pdf)
    r = _client(session_factory).post(
        f"/documents/{doc_id}/feedback",
        json={"kind": "fp", "type": "PERSON", "token": "[PERSON:aaaaaaaa]"})
    assert r.status_code == 201
    before_feedback = next(rec for rec in _records(session_factory, doc_id)
                           if rec.step == "detection_feedback")

    with session_factory() as s:
        delete_document(s, doc_id, mem_store, mem_index, actor="t")
        s.commit()

    after_delete = [rec for rec in _records(session_factory, doc_id)
                    if rec.step == "detection_feedback"]
    assert len(after_delete) == 1
    assert after_delete[0].hash == before_feedback.hash
    assert after_delete[0].payload == before_feedback.payload
    with session_factory() as s:
        assert verify_chain(s) == (True, None)


def _pause_the_first_lock(monkeypatch, paused: threading.Event,
                          resume: threading.Event) -> None:
    """Pause right after the first `audit.lock_chain` call across any
    session: whichever request (feedback or deletion) reaches the lock
    first, so the test controls which one wins the race. Re-entrant calls
    within the same transaction (``append`` takes the lock again) are not
    paused a second time."""
    real = audit.lock_chain
    fired = {"done": False}

    def wrapper(session):
        real(session)
        if not fired["done"]:
            fired["done"] = True
            paused.set()
            assert resume.wait(30), "never resumed"
    monkeypatch.setattr(audit, "lock_chain", wrapper)


def test_feedback_that_wins_the_lock_precedes_the_deletion(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf,
        monkeypatch):
    doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                      born_digital_pii_pdf)
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()
    _pause_the_first_lock(monkeypatch, paused, resume)

    def feedback_call():
        result["resp"] = _client(session_factory).post(
            f"/documents/{doc_id}/feedback", json={"kind": "fn", "type": "PERSON"})

    def deleting():
        with session_factory() as s:
            delete_document(s, doc_id, mem_store, mem_index, actor="t")
            s.commit()

    fb = run(errors, "feedback", feedback_call)
    assert paused.wait(10)
    dele = run(errors, "delete", deleting)
    try:
        wait_for_a_lock_waiter(session_factory)
    finally:
        resume.set()
        fb.join(30)
        dele.join(30)

    assert not errors, errors
    assert result["resp"].status_code == 201

    steps = [rec.step for rec in _records(session_factory, doc_id)]
    assert "detection_feedback" in steps and "delete" in steps
    assert steps.index("detection_feedback") < steps.index("delete")
    with session_factory() as s:
        assert verify_chain(s) == (True, None)
        assert current_state(s, doc_id) == State.DELETED


def test_a_deletion_that_wins_the_lock_refuses_the_feedback(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf,
        monkeypatch):
    doc_id = _prepare(session_factory, mem_store, mem_index, fake_embedder,
                      born_digital_pii_pdf)
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()
    _pause_the_first_lock(monkeypatch, paused, resume)

    def deleting():
        with session_factory() as s:
            delete_document(s, doc_id, mem_store, mem_index, actor="t")
            s.commit()

    def feedback_call():
        result["resp"] = _client(session_factory).post(
            f"/documents/{doc_id}/feedback", json={"kind": "fn", "type": "PERSON"})

    dele = run(errors, "delete", deleting)
    assert paused.wait(10)
    fb = run(errors, "feedback", feedback_call)
    try:
        wait_for_a_lock_waiter(session_factory)
    finally:
        resume.set()
        dele.join(30)
        fb.join(30)

    assert not errors, errors
    assert result["resp"].status_code == 410
    assert result["resp"].json() == {"detail": "document deleted"}

    steps = [rec.step for rec in _records(session_factory, doc_id)]
    assert "detection_feedback" not in steps
    with session_factory() as s:
        assert verify_chain(s) == (True, None)
        assert current_state(s, doc_id) == State.DELETED
