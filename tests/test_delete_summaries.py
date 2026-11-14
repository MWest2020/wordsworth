# SPDX-License-Identifier: MIT
"""#455: a deleted document's summary (`document_summaries`, LLM text derived
from its content) goes with it, counted as `summaries_removed` in the `deleted`
record, the API answer and the CLI output; a dry run counts it, a rerun over an
already-deleted document removes a leftover (`remove-renders`)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from wordsworth import dossiers, grants as grants_mod, roles, summaries
from wordsworth.api import create_app
from wordsworth.audit import current_state, verify_chain
from wordsworth.delete_cli import main
from wordsworth.deletion import delete_document
from wordsworth.dossier_deletion import delete_dossier
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.models import AuditRecord, DocumentSummary, DocumentText, GrantRecord
from wordsworth.object_store import InMemoryObjectStore
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State

KEY = "documents/" + "6c" * 32
KEY_OTHER = "documents/" + "7d" * 32
TEXT = "De aanvraag voor een dakkapel is afgewezen."


class _Model:
    def generate(self, query, sources):        # pragma: no cover - not used
        raise AssertionError("summarise, not generate")

    def summarise(self, text: str) -> str:
        return "Het besluit gaat over een dakkapel."


def _summarised(session, key):
    """A registered document with text and a summary made the real way."""
    doc = register(session, key)
    session.merge(DocumentText(document_id=doc.id, anonymized_text=TEXT))
    session.flush()
    assert summaries.for_document(session, _Model(), doc.id, "test") is not None
    return doc


def _seed_summary(session, document_id):
    """A summary row as an old deletion left it (written directly: the
    document has no text any more, so `summaries` would refuse to make one)."""
    session.merge(DocumentSummary(document_id=document_id, text="over een dakkapel",
                                  model="test"))


def _steps(session, document_id) -> list[str]:
    return list(session.execute(
        select(AuditRecord.step).where(AuditRecord.document_id == document_id)
        .order_by(AuditRecord.seq)).scalars())


def test_delete_after_a_summary_removes_it_and_counts_it(
        session_factory, mem_store, mem_index):
    with session_factory() as s:
        doc_id = _summarised(s, KEY).id
        s.commit()
    client = TestClient(create_app(
        session_factory=session_factory, store=mem_store, search_index=mem_index,
        key_provider=InMemoryKeyProvider()))

    r = client.delete(f"/documents/{doc_id}")
    assert r.status_code == 200
    assert r.json()["summaries_removed"] == 1

    with session_factory() as s:
        assert s.get(DocumentSummary, doc_id) is None
        rec = s.execute(select(AuditRecord).where(
            AuditRecord.document_id == doc_id, AuditRecord.step == "delete")
        ).scalar_one()
        assert rec.payload["summaries_removed"] == 1
        # a count, never the summary's text or model
        assert "dakkapel" not in json.dumps(rec.payload)
        # no text left, so no summary is made for a deleted document afterwards
        made = summaries.compute(s, _Model(), [doc_id], model="test")
        assert (made.made, made.without_text) == (0, 1)
        assert s.get(DocumentSummary, doc_id) is None


def test_dry_run_counts_the_summary_and_removes_nothing(session_factory, capsys):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    with session_factory() as s:
        doc_id = _summarised(s, KEY).id
        s.add(GrantRecord(
            grant_id=uuid4().hex, recipient="operator", allowed_types=[],
            document_id=None, status=grants_mod.ACTIVE,
            created_at=datetime.now(timezone.utc), revoked_at=None,
            expires_at=None, actor="t", domain=None, role=roles.ADMIN))
        s.commit()

    args = [str(doc_id), "--actor", "operator"]
    assert main(args + ["--dry-run"], session_factory=session_factory,
                store=store, index=index) == 0
    dry = json.loads(capsys.readouterr().out)["results"][0]
    assert dry["summaries_removed"] == 1
    with session_factory() as s:
        assert s.get(DocumentSummary, doc_id) is not None
        assert current_state(s, doc_id) == State.REGISTERED

    assert main(args, session_factory=session_factory, store=store, index=index) == 0
    real = json.loads(capsys.readouterr().out)["results"][0]
    assert real["summaries_removed"] == 1
    with session_factory() as s:
        assert s.get(DocumentSummary, doc_id) is None


def test_a_rerun_over_an_already_deleted_document_removes_a_leftover_summary(session):
    """A document deleted before #455 kept its summary; a rerun removes it,
    records that once as `remove-renders`, and touches no other document."""
    store, index = InMemoryObjectStore(), InMemoryIndex()
    doc, other = register(session, KEY), _summarised(session, KEY_OTHER)
    session.commit()
    delete_document(session, doc.id, store, index, actor="tester")
    session.commit()
    _seed_summary(session, doc.id)            # left behind by the old deletion
    session.commit()

    dry = delete_document(session, doc.id, store, index, actor="op", dry_run=True)
    assert dry.summaries_removed == 1
    assert session.get(DocumentSummary, doc.id) is not None

    counts = delete_document(session, doc.id, store, index, actor="op")
    session.commit()

    assert counts.summaries_removed == 1
    assert session.get(DocumentSummary, doc.id) is None
    assert session.get(DocumentSummary, other.id) is not None
    rec = session.execute(select(AuditRecord).where(
        AuditRecord.document_id == doc.id, AuditRecord.step == "remove-renders")
    ).scalar_one()
    assert (rec.from_state, rec.to_state) == ("deleted", "deleted")
    assert rec.payload == {"actor": "op", "renders_removed": 0,
                           "box_maps_removed": 0, "summaries_removed": 1}
    assert current_state(session, doc.id) == State.DELETED
    ok, bad = verify_chain(session)
    assert ok and bad is None

    before = _steps(session, doc.id)
    again = delete_document(session, doc.id, store, index, actor="op")
    session.commit()
    assert again.summaries_removed == 0
    assert _steps(session, doc.id) == before  # nothing left, nothing recorded


def test_a_dossier_deletion_removes_its_members_summaries(session):
    store, index = InMemoryObjectStore(), InMemoryIndex()
    dossier = dossiers.ensure(session, "zaak-samenvatting")
    doc, shared = _summarised(session, KEY), _summarised(session, KEY_OTHER)
    elsewhere = dossiers.ensure(session, "zaak-elders")
    dossiers.add(session, dossier.id, doc.id, actor="t")
    dossiers.add(session, dossier.id, shared.id, actor="t")
    dossiers.add(session, elsewhere.id, shared.id, actor="t")
    session.commit()

    dry = delete_dossier(session, dossier.id, store, index, actor="tester",
                         dry_run=True)
    assert dry.deleted == [str(doc.id)]
    assert session.get(DocumentSummary, doc.id) is not None

    report = delete_dossier(session, dossier.id, store, index, actor="tester")
    session.commit()

    assert report.deleted == [str(doc.id)]
    assert report.released == [str(shared.id)]
    assert session.get(DocumentSummary, doc.id) is None
    # a member that stays in another dossier keeps its content, summary included
    assert session.get(DocumentSummary, shared.id) is not None
    rec = session.execute(select(AuditRecord).where(
        AuditRecord.document_id == doc.id, AuditRecord.step == "delete")
    ).scalar_one()
    assert rec.payload["summaries_removed"] == 1
