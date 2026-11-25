# SPDX-License-Identifier: MIT
"""`pii_mappings` rows are written under the audit chain lock, in pseudonym
order (`docs/reference/lock-order.md`; #465 review, #504).

An anonymizer calls `put` in the order values appear in a text, before its
run holds the chain lock. While `put` inserted right away, the uncommitted
row was a lock held ahead of the chain lock, and three interleavings ended in
`DeadlockDetected`. `put` now only buffers; `write_pending` stores the rows
once the chain lock is held, and nothing else does
(`tests/test_mapping_buffer.py`)."""
from __future__ import annotations

import threading

from sqlalchemy import func, select, text

from race_setup import run
from reanon_helpers import BSN, new_key_provider, pdf
from test_mapping_delete_race import (A_LINE, B_LINE, _bsn_token, _delete,
                                      _nothing, _pausing, _processed)
from test_reanonymize_delete_race import _done_or_waiting
from wordsworth import pseudonym_registry
from wordsworth.audit import verify_chain
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import DocumentPseudonym, PiiMapping
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import ingest, process, reanonymize
from wordsworth.pseudonymizer import ReversibleAnonymizer
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

OTHER_BSN = "234567892"  # valid (elfproef); survives PDF text extraction
C_LINE = f"Derde brief, ook over BSN {BSN}, zonder bijlage."


def _bounded(session) -> None:
    session.execute(text("SET lock_timeout = '20s'"))


def _irreversibly_indexed(session_factory, store, index, embedder, line):
    """Indexed without a keyed token: what `reanonymize` then mints is new."""
    with session_factory() as s:
        doc_id = ingest(s, store, pdf(line)).id
        s.commit()
        assert process(s, doc_id, store, search_index=index,
                       embedder=embedder) == State.INDEXED
        s.commit()
    return doc_id


def _reanonymizing(session_factory, store, index, embedder, doc_id, make_anon):
    def go():
        with session_factory() as s:
            _bounded(s)
            assert reanonymize(s, doc_id, store, anonymizer=make_anon(s),
                               search_index=index, embedder=embedder) == State.INDEXED
            s.commit()
    return go


def _assert_linked_and_stored(session_factory, doc_ids, n_mappings):
    with session_factory() as s:
        for doc_id in doc_ids:
            for token in s.execute(select(DocumentPseudonym.pseudonym).where(
                    DocumentPseudonym.document_id == doc_id)).scalars():
                assert s.get(PiiMapping, token) is not None, token
        assert s.scalar(select(func.count()).select_from(PiiMapping)) == n_mappings
        assert verify_chain(s) == (True, None)


def test_a_mapping_put_back_does_not_wait_for_another_run(
        session_factory, fake_embedder):
    """The review's interleaving. L reanonymizes and has found the mapping of
    document D; D is deleted and the mapping goes; R reanonymizes and mints
    the same value. L, linking under the chain lock, stored the mapping
    again -- and waited for R's uncommitted row, while R waited for the chain
    lock. Nothing of R's is in the database before R holds the chain lock."""
    store, index, kp = InMemoryObjectStore(), InMemoryIndex(), new_key_provider()
    d = _processed(session_factory, store, index, fake_embedder, kp, A_LINE)
    with session_factory() as s:
        token = _bsn_token(s, d)
    left = _irreversibly_indexed(session_factory, store, index, fake_embedder, B_LINE)
    right = _irreversibly_indexed(session_factory, store, index, fake_embedder, C_LINE)
    errors = {}
    l_paused, l_resume = threading.Event(), threading.Event()
    r_paused, r_resume = threading.Event(), threading.Event()

    lt = run(errors, "L", _reanonymizing(
        session_factory, store, index, fake_embedder, left,
        lambda s: _pausing(kp, s, l_paused, l_resume)))
    assert l_paused.wait(10)
    try:
        _delete(session_factory, store, index, d)()
        with session_factory() as s:
            assert s.get(PiiMapping, token) is None
        rt = run(errors, "R", _reanonymizing(
            session_factory, store, index, fake_embedder, right,
            lambda s: _pausing(kp, s, r_paused, r_resume)))
        assert r_paused.wait(10)
        l_resume.set()
        _done_or_waiting(session_factory, lt)
    finally:
        l_resume.set()
        r_resume.set()
        lt.join(30)
        rt.join(30)

    assert not errors, errors
    with session_factory() as s:
        assert _bsn_token(s, left) == _bsn_token(s, right) == token
    _assert_linked_and_stored(session_factory, [left, right], 1)


class _PausesAfterFirstPut(PostgresMappingStore):
    paused: threading.Event
    resume: threading.Event

    def put(self, *args, **kwargs):
        super().put(*args, **kwargs)
        if not self.paused.is_set():
            self.paused.set()
            assert self.resume.wait(30), "never resumed"


def test_two_runs_minting_the_same_values_in_opposite_order(
        session_factory, fake_embedder):
    """One text holds value A then B, the other B then A, both new. Rows
    inserted in text order made each run hold the row the other needed."""
    store, index, kp = InMemoryObjectStore(), InMemoryIndex(), new_key_provider()
    one = _irreversibly_indexed(session_factory, store, index, fake_embedder,
                                f"Eerst BSN {BSN} en daarna BSN {OTHER_BSN}.")
    two = _irreversibly_indexed(session_factory, store, index, fake_embedder,
                                f"Eerst BSN {OTHER_BSN} en daarna BSN {BSN}.")
    errors, threads, resumes = {}, [], []

    def make_anon(paused, resume):
        def make(s):
            mapping = _PausesAfterFirstPut(s)
            mapping.paused, mapping.resume = paused, resume
            return ReversibleAnonymizer(kp, mapping, detect=_nothing)
        return make

    try:
        for name, doc_id in (("one", one), ("two", two)):
            paused, resume = threading.Event(), threading.Event()
            resumes.append(resume)
            threads.append(run(errors, name, _reanonymizing(
                session_factory, store, index, fake_embedder, doc_id,
                make_anon(paused, resume))))
            assert paused.wait(10)  # its first value is `put`, the second not
        resumes[0].set()
        _done_or_waiting(session_factory, threads[0])
    finally:
        for resume in resumes:
            resume.set()
        for thread in threads:
            thread.join(30)

    assert not errors, errors
    with session_factory() as s:
        assert len(pseudonym_registry.registered(s, one)) == 2
        assert pseudonym_registry.registered(s, one) == pseudonym_registry.registered(s, two)
    _assert_linked_and_stored(session_factory, [one, two], 2)


def test_process_and_reanonymize_minting_the_same_new_value(
        session_factory, fake_embedder):
    """#504: `reanonymize` held the new row and waited for the chain lock;
    a `process` from `registered` held the chain lock and waited for the
    row."""
    store, index, kp = InMemoryObjectStore(), InMemoryIndex(), new_key_provider()
    old = _irreversibly_indexed(session_factory, store, index, fake_embedder, A_LINE)
    with session_factory() as s:
        new = ingest(s, store, pdf(B_LINE)).id
        s.commit()
    errors, paused, resume = {}, threading.Event(), threading.Event()

    def processing():
        with session_factory() as s:
            _bounded(s)
            anon = ReversibleAnonymizer(kp, PostgresMappingStore(s), detect=_nothing)
            assert process(s, new, store, anonymizer=anon, search_index=index,
                           embedder=fake_embedder) == State.INDEXED
            s.commit()

    rean = run(errors, "reanonymize", _reanonymizing(
        session_factory, store, index, fake_embedder, old,
        lambda s: _pausing(kp, s, paused, resume)))
    assert paused.wait(10)
    proc = run(errors, "process", processing)
    try:
        _done_or_waiting(session_factory, proc)
    finally:
        resume.set()
        rean.join(30)
        proc.join(30)

    assert not errors, errors
    _assert_linked_and_stored(session_factory, [old, new], 1)
