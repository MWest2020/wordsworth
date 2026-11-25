# SPDX-License-Identifier: MIT
"""The pseudonym backfill links through `pseudonym_registry.link` (#465
review): beside a deletion it is the same race as `process`. A document from
before the registry carries a token in its text and no link; the backfill
adds the link. A deletion of the token's last linked holder that checks in
between sees no link yet and removes the mapping."""
from __future__ import annotations

import threading

from sqlalchemy import delete, text

from race_setup import run
from reanon_helpers import new_key_provider
from test_mapping_delete_race import (A_LINE, B_LINE, _assert_b_can_still_be_revealed,
                                      _bsn_token, _delete, _processed)
from test_reanonymize_delete_race import _done_or_waiting
from wordsworth import backfill_pseudonyms, pseudonym_registry
from wordsworth.deletion import delete_document
from wordsworth.models import DocumentPseudonym, DocumentText
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import current_state
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State


def _from_before_the_registry(session_factory, doc_id):
    with session_factory() as s:
        s.execute(delete(DocumentPseudonym)
                  .where(DocumentPseudonym.document_id == doc_id))
        s.commit()


def test_a_deletion_waits_for_a_backfilled_link(session_factory, fake_embedder,
                                                monkeypatch):
    store, index, kp = InMemoryObjectStore(), InMemoryIndex(), new_key_provider()
    a = _processed(session_factory, store, index, fake_embedder, kp, A_LINE)
    b = _processed(session_factory, store, index, fake_embedder, kp, B_LINE)
    with session_factory() as s:
        token = _bsn_token(s, a)
    _from_before_the_registry(session_factory, b)
    errors, result = {}, {}
    paused, resume = threading.Event(), threading.Event()
    real = pseudonym_registry.link

    def linked_not_committed(session, document_id, *args, **kwargs):
        added = real(session, document_id, *args, **kwargs)
        if document_id == b:
            paused.set()
            assert resume.wait(30), "never resumed"
        return added
    monkeypatch.setattr(pseudonym_registry, "link", linked_not_committed)

    def backfilling():
        result["run"] = backfill_pseudonyms.run(session_factory, dry_run=False)

    back = run(errors, "backfill", backfilling)
    assert paused.wait(10)
    dele = run(errors, "delete", _delete(session_factory, store, index, a))
    try:
        # Without the chain lock in the link the deletion finishes here.
        _done_or_waiting(session_factory, dele)
    finally:
        resume.set()
        back.join(30)
        dele.join(30)

    assert not errors, errors
    assert result["run"][0] >= 1
    _assert_b_can_still_be_revealed(session_factory, kp, token, a, b)


def test_the_backfill_registers_nothing_for_a_deleted_document(
        session_factory, fake_embedder):
    """Its text is read again under the row lock; a dry run writes nothing."""
    store, index, kp = InMemoryObjectStore(), InMemoryIndex(), new_key_provider()
    a = _processed(session_factory, store, index, fake_embedder, kp, A_LINE)
    b = _processed(session_factory, store, index, fake_embedder, kp, B_LINE)
    _from_before_the_registry(session_factory, a)
    _from_before_the_registry(session_factory, b)
    assert backfill_pseudonyms.run(session_factory, dry_run=True)[0] == 2
    with session_factory() as s:
        assert pseudonym_registry.registered(s, a) == set()
        s.execute(text("SET lock_timeout = '2s'"))
        delete_document(s, a, store, index, actor="t")
        s.commit()
    documents, rows = backfill_pseudonyms.run(session_factory, dry_run=False)
    assert documents == 1 and rows >= 1
    with session_factory() as s:
        assert pseudonym_registry.registered(s, a) == set()
        assert _bsn_token(s, b)
    assert backfill_pseudonyms.run(session_factory, dry_run=False) == (1, 0)


def test_a_deletion_between_the_read_and_the_link_waits_for_the_backfill(
        session_factory, fake_embedder, monkeypatch):
    """The backfill holds the row FOR SHARE from before it reads the text
    until it commits the link. A deletion arriving in between waits, and
    then removes the link with the rest. Without the row lock the deletion
    finishes between the read and the link, and the backfill registers
    tokens for a document that is already deleted."""
    store, index, kp = InMemoryObjectStore(), InMemoryIndex(), new_key_provider()
    a = _processed(session_factory, store, index, fake_embedder, kp, A_LINE)
    b = _processed(session_factory, store, index, fake_embedder, kp, B_LINE)
    _from_before_the_registry(session_factory, a)
    with session_factory() as s:
        a_text = s.get(DocumentText, a).anonymized_text
        token = _bsn_token(s, b)
    errors, paused, resume = {}, threading.Event(), threading.Event()
    real = pseudonym_registry.tokens_in

    def read_not_linked(text_):  # the backfill read A's text, linked nothing yet
        if text_ == a_text and not paused.is_set():
            paused.set()
            assert resume.wait(30), "never resumed"
        return real(text_)
    monkeypatch.setattr(pseudonym_registry, "tokens_in", read_not_linked)

    back = run(errors, "backfill",
               lambda: backfill_pseudonyms.run(session_factory, dry_run=False))
    assert paused.wait(10)
    dele = run(errors, "delete", _delete(session_factory, store, index, a))
    try:
        _done_or_waiting(session_factory, dele)
    finally:
        resume.set()
        back.join(30)
        dele.join(30)

    assert not errors, errors
    with session_factory() as s:
        assert current_state(s, a) == State.DELETED
        assert pseudonym_registry.registered(s, a) == set()
    _assert_b_can_still_be_revealed(session_factory, kp, token, a, b)
