# SPDX-License-Identifier: MIT
"""Deleting a dossier (delete-dossiers): `delete_dossier`, the API, and what
each touched document keeps. The CLI (`wordsworth-delete --dossier`) has its
own tests alongside the document CLI, in `test_delete_cli.py`.

Mirrors `test_delete_documents.py`: a shared document keeps its content and
its other membership, an exclusive one is deleted, an empty dossier just
goes, and the guard is the one document deletion uses.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth import dossiers, grants as grants_mod, roles
from wordsworth.api import create_app
from wordsworth.audit import current_state, verify_chain
from wordsworth.dossier_deletion import DossierDeletionError, delete_dossier
from wordsworth.models import AuditRecord, Dossier, DossierDocument, GrantRecord, Topic
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import dossiers_of, register
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

KEY_A = "documents/" + "a1" * 32
KEY_B = "documents/" + "b2" * 32


def _now():
    return datetime.now(timezone.utc)


def _grant(recipient, *, role=None):
    return GrantRecord(
        grant_id=uuid4().hex, recipient=recipient, allowed_types=[],
        document_id=None, status=grants_mod.ACTIVE, created_at=_now(),
        revoked_at=None, expires_at=None, actor="t", domain=None, role=role,
    )


# --- 1. Deleting a dossier ---------------------------------------------------

def test_a_dossier_of_several_exclusive_documents_is_fully_deleted(session):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    dossier = dossiers.ensure(session, "zaak-a")
    a, b = register(session, KEY_A), register(session, KEY_B)
    session.flush()
    store.put(KEY_A, b"a"), store.put(KEY_B, b"b")
    dossiers.add(session, dossier.id, a.id, actor="t")
    dossiers.add(session, dossier.id, b.id, actor="t")
    index.index(str(a.id), "tekst a", KEY_A, dossiers=[str(dossier.id)])
    index.index(str(b.id), "tekst b", KEY_B, dossiers=[str(dossier.id)])
    session.commit()

    report = delete_dossier(session, dossier.id, store, index, actor="tester")
    session.commit()

    assert set(report.deleted) == {str(a.id), str(b.id)}
    assert report.released == []
    assert report.topics == 0
    for doc in (a, b):
        assert current_state(session, doc.id) == State.DELETED
    assert not store.exists(KEY_A) and not store.exists(KEY_B)
    assert not index.exists(str(a.id)) and not index.exists(str(b.id))
    assert session.get(Dossier, dossier.id) is None
    assert session.execute(
        select(DossierDocument).where(DossierDocument.dossier_id == dossier.id)
    ).first() is None


def test_a_shared_document_keeps_its_content_and_its_other_membership(session):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doomed, kept = dossiers.ensure(session, "zaak-doomed"), dossiers.ensure(session, "zaak-kept")
    shared = register(session, KEY_A)
    session.flush()
    store.put(KEY_A, b"a")
    dossiers.add(session, doomed.id, shared.id, actor="t")
    dossiers.add(session, kept.id, shared.id, actor="t")
    index.index(str(shared.id), "tekst", KEY_A, dossiers=[str(doomed.id), str(kept.id)])
    session.commit()

    report = delete_dossier(session, doomed.id, store, index, actor="tester")
    session.commit()

    assert report.deleted == []
    assert report.released == [str(shared.id)]
    assert report.topics == 0
    # content untouched
    assert store.exists(KEY_A)
    assert index.exists(str(shared.id))
    assert current_state(session, shared.id).value != "deleted"
    # the other membership survives, this one does not
    assert dossiers_of(session, shared.id) == [str(kept.id)]
    # a search scoped to the surviving dossier is unchanged; one scoped to the
    # deleted dossier no longer finds it
    assert index.search("tekst", only=[str(kept.id)])
    assert index.search("tekst", only=[str(doomed.id)]) == []
    assert index._dossiers[str(shared.id)] == {str(kept.id)}
    assert session.get(Dossier, doomed.id) is None


def test_an_empty_dossier_is_removed_and_no_document_changes(session):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doc = register(session, KEY_A)
    other = dossiers.ensure(session, "andere-zaak")
    dossiers.add(session, other.id, doc.id, actor="t")
    empty = dossiers.ensure(session, "leeg")
    session.commit()

    report = delete_dossier(session, empty.id, store, index, actor="tester")
    session.commit()

    assert report.as_dict() == {"deleted": [], "released": [], "topics": 0}
    assert session.get(Dossier, empty.id) is None
    assert dossiers_of(session, doc.id) == [str(other.id)]


def test_one_dossier_deleted_record_per_document_touched(session):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doomed, kept = dossiers.ensure(session, "zaak-doomed"), dossiers.ensure(session, "zaak-kept")
    exclusive, shared = register(session, KEY_A), register(session, KEY_B)
    session.flush()
    store.put(KEY_A, b"a"), store.put(KEY_B, b"b")
    dossiers.add(session, doomed.id, exclusive.id, actor="t")
    dossiers.add(session, doomed.id, shared.id, actor="t")
    dossiers.add(session, kept.id, shared.id, actor="t")
    index.index(str(exclusive.id), "x", KEY_A, dossiers=[str(doomed.id)])
    index.index(str(shared.id), "y", KEY_B, dossiers=[str(doomed.id), str(kept.id)])
    session.commit()

    delete_dossier(session, doomed.id, store, index, actor="tester")
    session.commit()

    for doc_id, released in ((exclusive.id, False), (shared.id, True)):
        rec = session.execute(
            select(AuditRecord).where(AuditRecord.document_id == doc_id,
                                      AuditRecord.step == "dossier-deleted")
        ).scalar_one()
        assert rec.payload["dossier_id"] == str(doomed.id)
        assert rec.payload["actor"] == "tester"
        assert rec.payload["action"] == ("released" if released else "deleted")
        assert str(doomed.id) in json.dumps(rec.payload)  # ids are fine...
        assert "zaak-doomed" not in json.dumps(rec.payload)  # ...no NAME

    ok, bad = verify_chain(session)
    assert ok and bad is None


def _topic(dossier_id, name="onderwerp"):
    return Topic(dossier_id=dossier_id, computed_name=name, computed_at=_now(),
                document_count=1)


def test_a_dossier_with_topics_is_deleted_along_with_them(session):
    """The bug this change fixes: `topics` used to survive the dossier and
    the delete failed with `ForeignKeyViolation` on `topics_dossier_id_fkey`.
    """
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doomed = dossiers.ensure(session, "zaak-met-onderwerpen")
    kept = dossiers.ensure(session, "andere-zaak")
    doomed_topic = _topic(doomed.id)
    kept_topic = _topic(kept.id)
    session.add_all([doomed_topic, kept_topic])
    session.commit()
    doomed_topic_id, kept_topic_id = doomed_topic.id, kept_topic.id

    report = delete_dossier(session, doomed.id, store, index, actor="tester")
    session.commit()

    assert report.topics == 1
    assert session.get(Topic, doomed_topic_id) is None
    assert session.get(Topic, kept_topic_id) is not None
    assert session.get(Dossier, doomed.id) is None


class _FlakyIndex(InMemoryIndex):
    """An index that fails once, so the rerun scenario can be driven on
    purpose rather than waited for -- same device as
    `test_delete_documents._FlakyIndex`."""

    def __init__(self):
        super().__init__()
        self.fail = True

    def exists(self, document_id):
        if self.fail:
            raise RuntimeError("index down")
        return super().exists(document_id)


def test_a_failed_deletion_leaves_the_topics_in_place(session):
    store, index = InMemoryObjectStore(), _FlakyIndex()
    dossier = dossiers.ensure(session, "zaak")
    doc = register(session, KEY_A)
    session.flush()
    store.put(KEY_A, b"a")
    dossiers.add(session, dossier.id, doc.id, actor="t")
    topic = _topic(dossier.id)
    session.add(topic)
    session.commit()
    topic_id = topic.id
    index.index(str(doc.id), "tekst", KEY_A, dossiers=[str(dossier.id)])

    with pytest.raises(RuntimeError):
        delete_dossier(session, dossier.id, store, index, actor="tester")
    session.rollback()
    assert session.get(Dossier, dossier.id) is not None
    assert session.get(Topic, topic_id) is not None

    index.fail = False
    report = delete_dossier(session, dossier.id, store, index, actor="tester")
    session.commit()
    assert report.topics == 1
    assert session.get(Dossier, dossier.id) is None
    assert session.get(Topic, topic_id) is None


def test_unknown_dossier_is_refused(session):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with pytest.raises(DossierDeletionError):
        delete_dossier(session, uuid4(), store, index, actor="tester")


# --- 2. Authorisation (over the API, same guard as document deletion) ------

def _app(session_factory, **kw):
    opts = {"api_keys": {"k-beheerder": "beheerder-caller",
                        "k-issuer": "issuer-caller", "k-nobody": "nobody-caller"},
           "grant_issuer_labels": ["issuer-caller"]}
    opts.update(kw)
    return TestClient(create_app(
        session_factory=session_factory, store=InMemoryObjectStore(),
        search_index=InMemoryIndex(), **opts))


def test_a_beheerder_deletes_a_dossier(session_factory):
    with session_factory() as s:
        dossier = dossiers.ensure(s, "zaak")
        s.add(_grant("beheerder-caller", role=roles.ADMIN))
        s.commit()
        dossier_id = dossier.id
    r = _app(session_factory).delete(f"/dossiers/{dossier_id}",
                                     headers={"X-API-Key": "k-beheerder"})
    assert r.status_code == 200
    with session_factory() as s:
        assert s.get(Dossier, dossier_id) is None


def test_an_issuer_label_deletes_a_dossier(session_factory):
    with session_factory() as s:
        dossier = dossiers.ensure(s, "zaak")
        s.commit()
        dossier_id = dossier.id
    r = _app(session_factory).delete(f"/dossiers/{dossier_id}",
                                     headers={"X-API-Key": "k-issuer"})
    assert r.status_code == 200


def test_anyone_else_is_refused_and_nothing_is_removed(session_factory):
    with session_factory() as s:
        dossier = dossiers.ensure(s, "zaak")
        doc = register(s, KEY_A)
        s.flush()
        dossiers.add(s, dossier.id, doc.id, actor="t")
        s.commit()
        dossier_id, doc_id = dossier.id, doc.id
    r = _app(session_factory).delete(f"/dossiers/{dossier_id}",
                                     headers={"X-API-Key": "k-nobody"})
    assert r.status_code == 403
    with session_factory() as s:
        assert s.get(Dossier, dossier_id) is not None
        assert s.execute(
            select(DossierDocument).where(DossierDocument.dossier_id == dossier_id)
        ).first() is not None
        assert s.execute(
            select(AuditRecord).where(AuditRecord.document_id == doc_id,
                                      AuditRecord.step == "dossier-deleted")
        ).first() is None


def test_an_unknown_dossier_is_404(session_factory):
    r = _app(session_factory).delete(f"/dossiers/{uuid4()}",
                                     headers={"X-API-Key": "k-issuer"})
    assert r.status_code == 404
