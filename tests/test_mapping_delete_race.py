# SPDX-License-Identifier: MIT
"""#465: a deletion must not remove a `pii_mappings` row that a concurrent
`process` or `reanonymize` of ANOTHER document is about to rely on.

The mapping store is global: one value is one token everywhere. Document A is
the last committed holder of the token for a BSN; document B, with the same
BSN, is being anonymised. B's `put` finds the row and inserts nothing, and B's
own `document_pseudonyms` rows are not committed yet, so A's deletion saw the
row as orphaned and removed it -- B's token could then never be revealed.

Two interleavings, one per order the two can take the audit chain lock in
(`docs/reference/lock-order.md`): linking and removing both happen under it."""
from __future__ import annotations

import threading

from sqlalchemy import select, text

from race_setup import run
from reanon_helpers import BSN, new_key_provider, pdf
from test_reanonymize_delete_race import _done_or_waiting
from wordsworth.audit import current_state, verify_chain
from wordsworth.crypto import decrypt
from wordsworth.deletion import delete_document
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import DocumentPseudonym, PiiMapping
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import ingest, process, reanonymize
from wordsworth.pseudonymizer import ReversibleAnonymizer
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

A_LINE = f"Brief aan de raad over BSN {BSN} van de aanvrager."
B_LINE = f"Tweede brief, opnieuw over BSN {BSN}, met een bijlage."


def _nothing(_text):
    return []


def _bounded(session) -> None:
    session.execute(text("SET lock_timeout = '20s'"))


class _PausesAfterAnonymize(ReversibleAnonymizer):
    """Holds right after `anonymize`: every `put` is done (a no-op for a
    value another document already minted), nothing is linked yet."""

    paused: threading.Event
    resume: threading.Event

    def anonymize(self, text):
        result = super().anonymize(text)
        self.paused.set()
        assert self.resume.wait(30), "never resumed"
        return result


def _pausing(kp, session, paused, resume):
    anon = _PausesAfterAnonymize(kp, PostgresMappingStore(session), detect=_nothing)
    anon.paused, anon.resume = paused, resume
    return anon


def _processed(session_factory, store, index, embedder, kp, line):
    with session_factory() as s:
        doc_id = ingest(s, store, pdf(line)).id
        s.commit()
        anon = ReversibleAnonymizer(kp, PostgresMappingStore(s), detect=_nothing)
        assert process(s, doc_id, store, anonymizer=anon, search_index=index,
                       embedder=embedder) == State.INDEXED
        s.commit()
    return doc_id


def _bsn_token(session, document_id) -> str:
    tokens = session.execute(
        select(DocumentPseudonym.pseudonym)
        .where(DocumentPseudonym.document_id == document_id,
               DocumentPseudonym.pseudonym.like("[BSN:%"))).scalars().all()
    assert len(tokens) == 1, tokens
    return tokens[0]


def _assert_b_can_still_be_revealed(session_factory, kp, token, a, b):
    with session_factory() as s:
        assert current_state(s, a) == State.DELETED
        assert _bsn_token(s, b) == token
        row = s.get(PiiMapping, token)
        assert row is not None, "the mapping B relies on was deleted with A"
        assert decrypt(kp.key(row.key_id).material, row.ciphertext,
                       row.nonce) == BSN
        assert verify_chain(s) == (True, None)


def _delete(session_factory, store, index, doc_id):
    def go():
        with session_factory() as s:
            _bounded(s)
            delete_document(s, doc_id, store, index, actor="t")
            s.commit()
    return go


def test_a_deletion_keeps_the_mapping_a_running_process_links(
        session_factory, fake_embedder):
    """`process` of B from `registered`: it holds the chain lock from its
    first record on. The deletion of A removed the mapping before it waited
    for that lock; now it takes the lock first, and then sees B's link."""
    store, index, kp = InMemoryObjectStore(), InMemoryIndex(), new_key_provider()
    a = _processed(session_factory, store, index, fake_embedder, kp, A_LINE)
    with session_factory() as s:
        token = _bsn_token(s, a)
        b = ingest(s, store, pdf(B_LINE)).id
        s.commit()
    errors, paused, resume = {}, threading.Event(), threading.Event()

    def processing():
        with session_factory() as s:
            _bounded(s)
            assert process(s, b, store, anonymizer=_pausing(kp, s, paused, resume),
                           search_index=index, embedder=fake_embedder) == State.INDEXED
            s.commit()

    proc = run(errors, "process", processing)
    assert paused.wait(10)
    dele = run(errors, "delete", _delete(session_factory, store, index, a))
    try:
        _done_or_waiting(session_factory, dele)
    finally:
        resume.set()
        proc.join(30)
        dele.join(30)

    assert not errors, errors
    _assert_b_can_still_be_revealed(session_factory, kp, token, a, b)

    # The last holder gone, the mapping goes with it, as before.
    _delete(session_factory, store, index, b)()
    with session_factory() as s:
        assert s.get(PiiMapping, token) is None


def test_a_mapping_deleted_before_the_link_is_put_back(
        session_factory, fake_embedder):
    """`reanonymize` of B holds no chain lock while it anonymises, so the
    deletion of A runs to its end in between and removes the mapping B's
    `put` had found. B notices when it links, under the chain lock, and
    stores the mapping again."""
    store, index, kp = InMemoryObjectStore(), InMemoryIndex(), new_key_provider()
    a = _processed(session_factory, store, index, fake_embedder, kp, A_LINE)
    with session_factory() as s:
        token = _bsn_token(s, a)
        b = ingest(s, store, pdf(B_LINE)).id
        s.commit()
        # Irreversible first: B holds no keyed token for the BSN yet.
        assert process(s, b, store, search_index=index,
                       embedder=fake_embedder) == State.INDEXED
        s.commit()
        assert s.get(DocumentPseudonym, (b, token)) is None
    errors, paused, resume = {}, threading.Event(), threading.Event()

    def reanonymizing():
        with session_factory() as s:
            _bounded(s)
            assert reanonymize(
                s, b, store, anonymizer=_pausing(kp, s, paused, resume),
                search_index=index, embedder=fake_embedder) == State.INDEXED
            s.commit()

    rean = run(errors, "reanonymize", reanonymizing)
    assert paused.wait(10)
    try:
        _delete(session_factory, store, index, a)()  # commits: nothing blocks it
        with session_factory() as s:
            assert s.get(PiiMapping, token) is None  # A was its only holder
    finally:
        resume.set()
        rean.join(30)

    assert not errors, errors
    _assert_b_can_still_be_revealed(session_factory, kp, token, a, b)
