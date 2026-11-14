# SPDX-License-Identifier: MIT
"""#451 review: the renders are listed before anything irreversible, a
superseded copy's redacted PDF is refused like its reveal, and the console
names a deleted document instead of pointing at a box map."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth import console_pdf
from wordsworth.api import create_app
from wordsworth.audit import current_state
from wordsworth.deletion import delete_document
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.models import AuditRecord, BoxMap, DocumentSummary, DocumentText
from wordsworth.object_store import InMemoryObjectStore, ObjectStoreError
from wordsworth.pdf_redaction import redacted_cache_key
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State
from wordsworth.supersession import supersede

KEY = "documents/" + "6c" * 32


class _NoListStore(InMemoryObjectStore):
    """An S3 identity without ListObjectsV2: every listing fails."""

    def iter_objects(self, prefix):
        raise ObjectStoreError(f"list {prefix!r} failed: AccessDenied")


def _box_map(document_id):
    return BoxMap(document_id=document_id, boxmap_hash="h" * 64, lists_hash=None,
                  boxes=[])


def test_a_listing_failure_removes_nothing_and_keeps_the_state(session):
    store, index = _NoListStore(), InMemoryIndex()
    doc = register(session, KEY)
    session.flush()
    store.put(KEY, b"bytes")
    store.put(redacted_cache_key(doc.id, 1, "h" * 64), b"%PDF-1.4")
    session.add(DocumentText(document_id=doc.id, anonymized_text="tekst"))
    session.add(_box_map(doc.id))
    session.add(DocumentSummary(document_id=doc.id, text="samenvatting", model="t"))
    index.index(str(doc.id), "tekst", KEY)
    session.commit()

    with pytest.raises(ObjectStoreError):
        delete_document(session, doc.id, store, index, actor="tester")
    session.rollback()

    # nothing irreversible happened: the index entry and both objects are there
    assert index.exists(str(doc.id))
    assert store.exists(KEY)
    assert store.exists(redacted_cache_key(doc.id, 1, "h" * 64))
    assert session.get(DocumentText, doc.id) is not None
    assert session.get(BoxMap, doc.id) is not None
    assert session.get(DocumentSummary, doc.id) is not None  # #455
    assert current_state(session, doc.id) == State.REGISTERED
    assert session.execute(select(AuditRecord).where(
        AuditRecord.document_id == doc.id, AuditRecord.step == "delete")
    ).first() is None


def test_a_superseded_copy_redacted_pdf_is_409(legacy_copies):
    store = InMemoryObjectStore()
    with legacy_copies() as s:
        survivor, copy = register(s, KEY), register(s, KEY)
        s.flush()
        s.add(_box_map(copy.id))
        supersede(s, copy.id, survivor.id, actor="dedupe")
        s.commit()
        copy_id, survivor_id = copy.id, survivor.id
    client = TestClient(create_app(session_factory=legacy_copies, store=store,
                                   key_provider=InMemoryKeyProvider()))
    r = client.get(f"/documents/{copy_id}/redacted.pdf")
    assert r.status_code == 409
    assert str(survivor_id) in r.json()["detail"]


def test_the_console_says_a_deleted_document_is_deleted(session_factory):
    with session_factory() as s:
        doc = register(s, KEY)
        s.commit()
        delete_document(s, doc.id, InMemoryObjectStore(), InMemoryIndex(), actor="t")
        s.commit()
        st = console_pdf.state(s, doc.id, "lists-now")
    assert st == {"available": False, "reason": console_pdf.DELETED,
                  "why": "Dit document is verwijderd."}
