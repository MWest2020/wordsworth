# SPDX-License-Identifier: MIT
"""#451: a deleted document's cached redacted PDFs and box map go with it, and
neither `GET .../redacted.pdf` nor `POST .../reveal.pdf` answers for it. The
first test drives the real pipeline and routes; the rest seed by hand."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth import dossiers, grants as grants_mod, roles
from wordsworth.api import create_app
from wordsworth.audit import current_state, verify_chain
from wordsworth.delete_cli import main
from wordsworth.deletion import delete_document
from wordsworth.dossier_deletion import delete_dossier
from wordsworth.grants import InMemoryGrantStore
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import PostgresMappingStore
from wordsworth.models import AuditRecord, BoxMap, GrantRecord
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pdf_redaction import redacted_cache_key, redacted_prefix
from wordsworth.pipeline import ingest, process, register
from wordsworth.pseudonymizer import Pseudonymizer
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

KEY = "documents/" + "4a" * 32
KEY_OTHER = "documents/" + "5b" * 32


def _renders(store, document_id) -> list[str]:
    return [k for k, _ in store.iter_objects(redacted_prefix(document_id))]


def _seed_render(session, store, document_id, versions=(1,)):
    """A box map row and one cached render per version, as the GET leaves them."""
    session.merge(BoxMap(document_id=document_id, boxmap_hash="h" * 64,
                         lists_hash=None, boxes=[]))
    for version in versions:
        store.put(redacted_cache_key(document_id, version, "h" * 64), b"%PDF-1.4")


def _steps(session, document_id) -> list[str]:
    return list(session.execute(
        select(AuditRecord.step).where(AuditRecord.document_id == document_id)
        .order_by(AuditRecord.seq)).scalars())


def test_delete_after_a_render_removes_it_and_the_routes_answer_410(
        session_factory, mem_store, mem_index, fake_embedder, born_digital_pii_pdf):
    kp = InMemoryKeyProvider()
    with session_factory() as s:
        doc = ingest(s, mem_store, born_digital_pii_pdf)
        s.commit()
        process(s, doc.id, mem_store,
                anonymizer=Pseudonymizer(kp, PostgresMappingStore(s)),
                search_index=mem_index, embedder=fake_embedder,
                key_provider=kp, mapping_store=PostgresMappingStore(s))
        s.commit()
        doc_id = doc.id
    gs = InMemoryGrantStore()
    grant = gs.issue("agent-x", ["EMAIL"], actor="mark", document_id=doc_id)
    client = TestClient(create_app(
        session_factory=session_factory, store=mem_store, search_index=mem_index,
        key_provider=kp, grant_store=gs))

    assert client.get(f"/documents/{doc_id}/redacted.pdf").status_code == 200
    assert len(_renders(mem_store, doc_id)) == 1

    r = client.delete(f"/documents/{doc_id}")
    assert r.status_code == 200
    assert r.json()["renders_removed"] == 1
    assert r.json()["box_maps_removed"] == 1

    assert _renders(mem_store, doc_id) == []
    with session_factory() as s:
        assert s.get(BoxMap, doc_id) is None
        rec = s.execute(select(AuditRecord).where(
            AuditRecord.document_id == doc_id, AuditRecord.step == "delete")
        ).scalar_one()
        assert rec.payload["renders_removed"] == 1
        assert rec.payload["box_maps_removed"] == 1

    got = client.get(f"/documents/{doc_id}/redacted.pdf")
    assert got.status_code == 410
    assert _renders(mem_store, doc_id) == []  # refused before any re-render
    revealed = client.post(f"/documents/{doc_id}/reveal.pdf",
                           json={"grant_id": grant.grant_id})
    assert revealed.status_code == 410


def test_a_render_left_in_the_cache_is_not_served(session_factory, mem_store):
    """The state is checked BEFORE the cache: even a leftover box map and
    render (written before this fix, or by a request racing the deletion)
    answer 410, not the cached bytes."""
    with session_factory() as s:
        doc = register(s, KEY)
        s.commit()
        delete_document(s, doc.id, mem_store, InMemoryIndex(), actor="t")
        s.commit()
        _seed_render(s, mem_store, doc.id)
        s.commit()
        doc_id = doc.id
    client = TestClient(create_app(session_factory=session_factory, store=mem_store,
                                   key_provider=InMemoryKeyProvider()))
    assert client.get(f"/documents/{doc_id}/redacted.pdf").status_code == 410


def test_a_dossier_deletion_removes_its_members_renders(session):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    dossier = dossiers.ensure(session, "zaak-renders")
    doc = register(session, KEY)
    session.flush()
    dossiers.add(session, dossier.id, doc.id, actor="t")
    _seed_render(session, store, doc.id, versions=(1, 2))
    session.commit()

    report = delete_dossier(session, dossier.id, store, index, actor="tester")
    session.commit()

    assert report.deleted == [str(doc.id)]
    assert _renders(store, doc.id) == []
    assert session.get(BoxMap, doc.id) is None


def test_dry_run_counts_renders_and_box_map_and_removes_nothing(
        session_factory, capsys):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        doc = register(s, KEY)
        s.flush()
        _seed_render(s, store, doc.id, versions=(1, 2))
        s.add(GrantRecord(
            grant_id=uuid4().hex, recipient="operator", allowed_types=[],
            document_id=None, status=grants_mod.ACTIVE,
            created_at=datetime.now(timezone.utc), revoked_at=None,
            expires_at=None, actor="t", domain=None, role=roles.ADMIN))
        s.commit()
        doc_id = doc.id

    args = [str(doc_id), "--actor", "operator"]
    assert main(args + ["--dry-run"], session_factory=session_factory,
                store=store, index=index) == 0
    dry = json.loads(capsys.readouterr().out)["results"][0]
    assert (dry["renders_removed"], dry["box_maps_removed"]) == (2, 1)
    assert len(_renders(store, doc_id)) == 2
    with session_factory() as s:
        assert s.get(BoxMap, doc_id) is not None
        assert current_state(s, doc_id) == State.REGISTERED

    assert main(args, session_factory=session_factory, store=store, index=index) == 0
    real = json.loads(capsys.readouterr().out)["results"][0]
    assert (real["renders_removed"], real["box_maps_removed"]) == (2, 1)
    assert _renders(store, doc_id) == []
    with session_factory() as s:
        assert s.get(BoxMap, doc_id) is None


def test_a_rerun_over_an_already_deleted_document_removes_leftovers(session):
    """A document deleted before this fix kept its renders and box map; a
    rerun removes them, records that once, and touches no other document."""
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doc, other = register(session, KEY), register(session, KEY_OTHER)
    session.commit()
    delete_document(session, doc.id, store, index, actor="tester")
    session.commit()
    _seed_render(session, store, doc.id)      # left behind by the old deletion
    _seed_render(session, store, other.id)    # a live document's render
    session.commit()

    dry = delete_document(session, doc.id, store, index, actor="op", dry_run=True)
    assert (dry.renders_removed, dry.box_maps_removed) == (1, 1)
    assert len(_renders(store, doc.id)) == 1

    counts = delete_document(session, doc.id, store, index, actor="op")
    session.commit()

    assert (counts.renders_removed, counts.box_maps_removed) == (1, 1)
    assert _renders(store, doc.id) == []
    assert session.get(BoxMap, doc.id) is None
    assert len(_renders(store, other.id)) == 1
    assert session.get(BoxMap, other.id) is not None
    rec = session.execute(select(AuditRecord).where(
        AuditRecord.document_id == doc.id, AuditRecord.step == "remove-renders")
    ).scalar_one()
    assert (rec.from_state, rec.to_state) == ("deleted", "deleted")
    assert rec.payload == {"actor": "op", "renders_removed": 1, "box_maps_removed": 1}
    assert current_state(session, doc.id) == State.DELETED
    ok, bad = verify_chain(session)
    assert ok and bad is None

    before = _steps(session, doc.id)
    again = delete_document(session, doc.id, store, index, actor="op")
    session.commit()
    assert (again.renders_removed, again.box_maps_removed) == (0, 0)
    assert _steps(session, doc.id) == before  # nothing left, nothing recorded
