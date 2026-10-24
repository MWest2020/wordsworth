# SPDX-License-Identifier: MIT
"""document-deletion: who may, what goes, what stays, the trail, and retries.

The row and the earlier audit records always stay (the row stays, the content
goes -- `deletion.py`); only the content a document carries is removed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from wordsworth import grants as grants_mod
from wordsworth import roles
from wordsworth.api import create_app
from wordsworth.audit import current_state, verify_chain
from wordsworth.deletion import DeletionError, delete_document
from wordsworth.models import (
    AuditRecord, Document, DocumentPseudonym, DocumentText, GrantRecord, PiiMapping,
)
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

KEY = "documents/" + "de" * 32


def _now():
    return datetime.now(timezone.utc)


def _grant(recipient, *, document_id=None, role=None):
    return GrantRecord(
        grant_id=uuid4().hex, recipient=recipient, allowed_types=[],
        document_id=document_id, status=grants_mod.ACTIVE, created_at=_now(),
        revoked_at=None, expires_at=None, actor="t", domain=None, role=role,
    )


class _FlakyIndex(InMemoryIndex):
    """An index that fails once, so the rerun scenario can be driven on
    purpose rather than waited for."""

    def __init__(self):
        super().__init__()
        self.fail = True

    def exists(self, document_id):
        if self.fail:
            raise RuntimeError("index down")
        return super().exists(document_id)


# --- 2. Deleting a document --------------------------------------------------

def test_deletion_removes_the_six_kinds_and_keeps_the_row_and_the_trail(session):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doc = register(session, KEY)
    session.flush()
    store.put(KEY, b"bytes")
    session.add(DocumentText(document_id=doc.id, anonymized_text="tekst"))
    session.add(DocumentPseudonym(document_id=doc.id, pseudonym="[PERSON:aaaaaaaa]",
                                  source="minted", created_at=_now()))
    session.add(PiiMapping(pseudonym="[PERSON:aaaaaaaa]", ciphertext=b"c", nonce=b"n",
                           key_id="k1", norm_version=None, created_at=_now()))
    session.add(_grant("someone", document_id=doc.id))
    session.flush()
    index.index(str(doc.id), "tekst", KEY)
    session.commit()

    counts = delete_document(session, doc.id, store, index, actor="tester")
    session.commit()

    assert counts.as_dict() == {"object": 1, "text": 1, "pseudonyms": 1,
                                "mappings": 1, "index_entries": 1, "grants": 1}
    assert not store.exists(KEY)
    assert not index.exists(str(doc.id))
    assert index.search("tekst") == []
    assert session.get(DocumentText, doc.id) is None
    assert session.get(PiiMapping, "[PERSON:aaaaaaaa]") is None
    assert session.execute(
        select(GrantRecord).where(GrantRecord.document_id == doc.id)).first() is None
    # the row and the earlier audit record stay
    assert session.get(Document, doc.id) is not None
    assert current_state(session, doc.id) == State.DELETED
    steps = [r.step for r in session.execute(
        select(AuditRecord).where(AuditRecord.document_id == doc.id)
        .order_by(AuditRecord.seq)).scalars()]
    assert steps == ["register", "delete"]


def test_deleted_audit_record_carries_ids_and_counts_only(session):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doc = register(session, KEY)
    session.flush()
    store.put(KEY, b"bytes")
    session.commit()

    delete_document(session, doc.id, store, index, actor="tester")
    session.commit()

    rec = session.execute(
        select(AuditRecord).where(AuditRecord.document_id == doc.id,
                                  AuditRecord.step == "delete")).scalar_one()
    assert rec.payload == {"actor": "tester", "object": 1, "text": 0,
                           "pseudonyms": 0, "mappings": 0, "index_entries": 0,
                           "grants": 0}
    # no value, text, token or filename -- the payload is ids and counts only
    assert KEY not in json.dumps(rec.payload)

    ok, bad = verify_chain(session)
    assert ok and bad is None
    earlier = session.execute(
        select(AuditRecord).where(AuditRecord.document_id == doc.id,
                                  AuditRecord.step == "register")).scalar_one()
    assert earlier.to_state == "registered"  # unchanged by the deletion


def test_deleting_an_already_deleted_document_is_a_no_op(session):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doc = register(session, KEY)
    session.commit()
    delete_document(session, doc.id, store, index, actor="tester")
    session.commit()
    before = session.execute(
        select(func.count()).select_from(AuditRecord)
        .where(AuditRecord.document_id == doc.id)).scalar_one()

    counts = delete_document(session, doc.id, store, index, actor="tester")
    session.commit()

    after = session.execute(
        select(func.count()).select_from(AuditRecord)
        .where(AuditRecord.document_id == doc.id)).scalar_one()
    assert before == after
    assert counts.as_dict() == {"object": 0, "text": 0, "pseudonyms": 0,
                                "mappings": 0, "index_entries": 0, "grants": 0}


def test_a_failed_removal_is_a_hard_error_and_a_rerun_finishes(session):
    store, index = InMemoryObjectStore(), _FlakyIndex()
    doc = register(session, KEY)
    session.flush()
    store.put(KEY, b"bytes")
    index.index(str(doc.id), "tekst", KEY)
    session.commit()

    with pytest.raises(RuntimeError):
        delete_document(session, doc.id, store, index, actor="tester")
    session.rollback()
    assert current_state(session, doc.id) != State.DELETED
    assert session.execute(
        select(AuditRecord).where(AuditRecord.document_id == doc.id,
                                  AuditRecord.step == "delete")).first() is None
    assert store.exists(KEY)  # nothing removed on the failed attempt

    index.fail = False
    delete_document(session, doc.id, store, index, actor="tester")
    session.commit()
    assert current_state(session, doc.id) == State.DELETED
    assert not store.exists(KEY)


def test_unknown_document_is_refused(session):
    with pytest.raises(DeletionError):
        delete_document(session, uuid4(), InMemoryObjectStore(), InMemoryIndex(),
                        actor="tester")


def test_the_object_stays_while_another_live_document_still_claims_the_key(
        legacy_copies, session):
    """A superseded copy keeps its former object key (one-document-per-object);
    deleting the document that still claims it must not take the bytes out
    from under the other."""
    store, index = InMemoryObjectStore(), InMemoryIndex()
    store.put(KEY, b"bytes")
    a, b = register(session, KEY), register(session, KEY)
    session.commit()

    counts = delete_document(session, a.id, store, index, actor="t")
    session.commit()

    assert counts.object == 0
    assert store.exists(KEY)
    assert current_state(session, a.id) == State.DELETED
    assert current_state(session, b.id) != State.DELETED

    # once b is gone too, nothing claims the key any more
    delete_document(session, b.id, store, index, actor="t")
    session.commit()
    assert not store.exists(KEY)


def test_a_shared_mapping_stays_while_another_document_still_references_it(session):
    """The mapping store is global: one value, one token, across documents
    (mapping_store.py). Deleting one document's pseudonym row must not orphan
    a mapping another document still needs to resolve the same token."""
    store, index = InMemoryObjectStore(), InMemoryIndex()
    a = register(session, "documents/" + "11" * 32)
    b = register(session, "documents/" + "22" * 32)
    session.flush()
    session.add(PiiMapping(pseudonym="[PERSON:aaaaaaaa]", ciphertext=b"c", nonce=b"n",
                           key_id="k1", norm_version=None, created_at=_now()))
    session.add(DocumentPseudonym(document_id=a.id, pseudonym="[PERSON:aaaaaaaa]",
                                  source="minted", created_at=_now()))
    session.add(DocumentPseudonym(document_id=b.id, pseudonym="[PERSON:aaaaaaaa]",
                                  source="minted", created_at=_now()))
    session.commit()

    counts = delete_document(session, a.id, store, index, actor="t")
    session.commit()

    assert counts.pseudonyms == 1 and counts.mappings == 0
    assert session.get(PiiMapping, "[PERSON:aaaaaaaa]") is not None
    assert session.execute(
        select(DocumentPseudonym).where(DocumentPseudonym.document_id == a.id)
    ).first() is None


# --- 1. Authorisation (over the API) ----------------------------------------

def _app(session_factory, **kw):
    opts = {"api_keys": {"k-beheerder": "beheerder-caller",
                        "k-issuer": "issuer-caller", "k-nobody": "nobody-caller"},
           "grant_issuer_labels": ["issuer-caller"]}
    opts.update(kw)
    return TestClient(create_app(
        session_factory=session_factory, store=InMemoryObjectStore(),
        search_index=InMemoryIndex(), **opts))


def test_a_beheerder_deletes(session_factory):
    with session_factory() as s:
        doc = register(s, KEY)
        s.flush()
        s.add(_grant("beheerder-caller", role=roles.ADMIN))
        s.commit()
        doc_id = doc.id
    r = _app(session_factory).delete(f"/documents/{doc_id}",
                                     headers={"X-API-Key": "k-beheerder"})
    assert r.status_code == 200
    with session_factory() as s:
        assert current_state(s, doc_id) == State.DELETED


def test_an_issuer_label_deletes(session_factory):
    with session_factory() as s:
        doc = register(s, KEY)
        s.commit()
        doc_id = doc.id
    r = _app(session_factory).delete(f"/documents/{doc_id}",
                                     headers={"X-API-Key": "k-issuer"})
    assert r.status_code == 200
    with session_factory() as s:
        assert current_state(s, doc_id) == State.DELETED


def test_anyone_else_is_refused(session_factory):
    with session_factory() as s:
        doc = register(s, KEY)
        s.commit()
        doc_id = doc.id
    r = _app(session_factory).delete(f"/documents/{doc_id}",
                                     headers={"X-API-Key": "k-nobody"})
    assert r.status_code == 403
    with session_factory() as s:
        assert current_state(s, doc_id) == State.REGISTERED
        assert s.execute(
            select(AuditRecord).where(AuditRecord.document_id == doc_id,
                                      AuditRecord.step == "delete")).first() is None


def test_a_role_granted_elsewhere_does_not_count(session_factory):
    """Holding SOME role is not holding `beheerder` -- the grant must name it."""
    from wordsworth.key_audit_pg import PostgresKeyLifecycleAudit

    with session_factory() as s:
        roles.create(s, "HR", ["PERSON"], actor="t", audit=PostgresKeyLifecycleAudit(s))
        doc = register(s, KEY)
        s.flush()
        s.add(_grant("hr-caller", role="HR"))
        s.commit()
        doc_id = doc.id
    r = _app(session_factory, api_keys={
        "k-beheerder": "beheerder-caller", "k-issuer": "issuer-caller",
        "k-nobody": "nobody-caller", "k-hr": "hr-caller"},
    ).delete(f"/documents/{doc_id}", headers={"X-API-Key": "k-hr"})
    assert r.status_code == 403


def test_delete_unknown_document_is_404(session_factory):
    r = _app(session_factory).delete(f"/documents/{uuid4()}",
                                     headers={"X-API-Key": "k-issuer"})
    assert r.status_code == 404
