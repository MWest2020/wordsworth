# SPDX-License-Identifier: MIT
"""`wordsworth-delete` -- the CLI half of document-deletion.

Drives `wordsworth.delete_cli.main` itself (not just the pieces under it):
with `--dry-run` it prints the counts, removes nothing and writes no audit
record; the same call without `--dry-run` removes the document.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from wordsworth import grants as grants_mod
from wordsworth import roles
from wordsworth.audit import current_state
from wordsworth.delete_cli import main
from wordsworth.models import AuditRecord, DocumentText, GrantRecord
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

KEY = "documents/" + "ce" * 32


def _make_beheerder(session, label):
    session.add(GrantRecord(
        grant_id=uuid4().hex, recipient=label, allowed_types=[], document_id=None,
        status=grants_mod.ACTIVE, created_at=datetime.now(timezone.utc),
        revoked_at=None, expires_at=None, actor="t", domain=None, role=roles.ADMIN))


def test_dry_run_prints_counts_removes_nothing_writes_no_record(
        session_factory, capsys):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        doc = register(s, KEY)
        s.flush()
        store.put(KEY, b"bytes")
        s.add(DocumentText(document_id=doc.id, anonymized_text="tekst"))
        _make_beheerder(s, "operator")
        s.commit()
        doc_id = doc.id
    index.index(str(doc_id), "tekst", KEY)

    code = main([str(doc_id), "--dry-run", "--actor", "operator"],
               session_factory=session_factory, store=store, index=index)

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] is True
    assert report["results"] == [
        {"document_id": str(doc_id), "object": 1, "text": 1, "pseudonyms": 0,
         "mappings": 0, "index_entries": 1, "grants": 0}]
    # nothing removed
    assert store.exists(KEY)
    assert index.exists(str(doc_id))
    with session_factory() as s:
        assert s.get(DocumentText, doc_id) is not None
        assert current_state(s, doc_id) != State.DELETED
        assert s.execute(
            select(AuditRecord)
            .where(AuditRecord.document_id == doc_id, AuditRecord.step == "delete")
        ).first() is None


def test_the_same_call_without_dry_run_removes_the_document(session_factory, capsys):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        doc = register(s, KEY)
        s.flush()
        store.put(KEY, b"bytes")
        _make_beheerder(s, "operator")
        s.commit()
        doc_id = doc.id
    index.index(str(doc_id), "tekst", KEY)

    code = main([str(doc_id), "--actor", "operator"],
               session_factory=session_factory, store=store, index=index)

    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] is False
    assert not store.exists(KEY)
    assert not index.exists(str(doc_id))
    with session_factory() as s:
        assert current_state(s, doc_id) == State.DELETED


def test_a_caller_without_the_role_or_an_issuer_label_is_refused(session_factory):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        doc = register(s, KEY)
        s.commit()
        doc_id = doc.id

    code = main([str(doc_id), "--actor", "nobody"],
               session_factory=session_factory, store=store, index=index,
               issuer_labels=[])

    assert code == 1
    with session_factory() as s:
        assert current_state(s, doc_id) == State.REGISTERED


def test_an_issuer_label_may_delete_without_the_role(session_factory):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        doc = register(s, KEY)
        s.commit()
        doc_id = doc.id

    code = main([str(doc_id), "--actor", "ops-issuer"],
               session_factory=session_factory, store=store, index=index,
               issuer_labels=["ops-issuer"])

    assert code == 0
    with session_factory() as s:
        assert current_state(s, doc_id) == State.DELETED


def test_actor_is_required():
    with pytest.raises(SystemExit):
        main([str(uuid4())])


def test_a_malformed_document_id_is_refused():
    with pytest.raises(SystemExit):
        main(["not-a-uuid", "--actor", "operator"])
