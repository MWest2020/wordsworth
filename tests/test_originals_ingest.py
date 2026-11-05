# SPDX-License-Identifier: MIT
"""`originals-ingest-write`: `pipeline.ingest` registers before it writes, and
rolls back only the object it wrote itself (design.md's "caller's contract",
`OriginalsStore.put_original`'s `PutResult`). Tasks 1.1-1.3."""
from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import select

from wordsworth import pipeline as pipeline_mod
from wordsworth.document_keys import DocumentKeyRecord, DocumentKeys
from wordsworth.models import Document
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.originals_envelope import HEADER_MAGIC
from wordsworth.originals_store import OriginalsStore
from wordsworth.pipeline import ingest
from wordsworth.transit import FakeTransit


def _transit_for(name: str) -> FakeTransit:
    return FakeTransit()


def _store() -> OriginalsStore:
    return OriginalsStore(InMemoryObjectStore(), DocumentKeys(_transit_for))


# --- task 1.1: register before write ----------------------------------------

class _SpyOriginalsStore(OriginalsStore):
    """Records, at the moment `put_original` is called, whether the document
    row is already in the session -- the thing `register-first` promises."""

    def __init__(self, objects, keys):
        super().__init__(objects, keys)
        self.document_already_registered: bool | None = None

    def put_original(self, session, document_id, object_key, data):
        self.document_already_registered = (
            session.get(Document, document_id) is not None)
        return super().put_original(session, document_id, object_key, data)


def test_register_first(session):
    spy = _SpyOriginalsStore(InMemoryObjectStore(), DocumentKeys(_transit_for))
    doc = ingest(session, spy, b"%PDF-1.4 some bytes")

    assert spy.document_already_registered is True
    row = session.get(DocumentKeyRecord, doc.object_key)
    assert row.document_id == doc.id


# --- task 1.2: rollback deletes only what this call wrote ------------------

def _boom(*args, **kwargs):
    raise RuntimeError("dossier add failed")


def test_dossier_add_failure_after_a_write_leaves_no_object_and_no_document(
    session_factory, monkeypatch,
):
    store = _store()
    data = b"%PDF-1.4 rollback bytes"
    key = "documents/" + hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(pipeline_mod.dossiers, "add", _boom)

    with session_factory() as session:
        with pytest.raises(RuntimeError):
            ingest(session, store, data, dossier="zaak")
        session.rollback()

    with session_factory() as session:
        assert session.execute(select(Document)).scalars().all() == []
    assert not store.objects.exists(key)


def test_dossier_add_failure_on_unchanged_bytes_leaves_the_existing_object(
    session_factory, monkeypatch,
):
    store = _store()
    data = b"%PDF-1.4 unchanged bytes"

    with session_factory() as session:
        doc1 = ingest(session, store, data)
        session.commit()
        key = doc1.object_key

    monkeypatch.setattr(pipeline_mod.dossiers, "add", _boom)

    with session_factory() as session:
        with pytest.raises(RuntimeError):
            ingest(session, store, data, dossier="zaak")
        session.rollback()

    with session_factory() as session:
        assert store.get_original(session, key) == data


# --- task 1.3: sealed at rest -------------------------------------------

def test_stored_object_is_sealed_ciphertext(session, born_digital_pdf):
    store = _store()
    doc = ingest(session, store, born_digital_pdf)

    raw = store.objects.get_raw(doc.object_key)
    assert raw.startswith(HEADER_MAGIC)
    assert b"born-digital" not in raw
    assert store.get_original(session, doc.object_key) == born_digital_pdf


def test_identical_bytes_ingested_twice_give_one_document_one_key_row(
    session_factory, born_digital_pdf,
):
    store = _store()
    with session_factory() as session:
        doc1 = ingest(session, store, born_digital_pdf)
        session.commit()
        before = store.objects.get_raw(doc1.object_key)

    with session_factory() as session:
        doc2 = ingest(session, store, born_digital_pdf)
        session.commit()
        after = store.objects.get_raw(doc2.object_key)

    assert doc1.id == doc2.id
    assert before == after
    with session_factory() as session:
        rows = session.execute(
            select(DocumentKeyRecord)
            .where(DocumentKeyRecord.object_key == doc1.object_key)
        ).scalars().all()
        assert len(rows) == 1
