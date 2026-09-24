# SPDX-License-Identifier: MIT
"""Retiring a copy (one-document-per-object, release 1).

On 2026-09-24 production held 173 documents that were copies of an object
another document already was. These tests pin what retiring one means: it
keeps its history, leaves search and its dossiers as recorded acts, passes on
any dossier only it was in, and answers for itself as `superseded`.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from wordsworth import dossiers
from wordsworth.api import create_app
from wordsworth.backfill_dossier import orphans
from wordsworth.models import AuditRecord, Document, DossierDocument
from wordsworth.pipeline import current_state, ingest, live_document_for, register
from wordsworth.search_index import InMemoryIndex
from wordsworth.states import State
from wordsworth.supersession import SupersessionError, supersede

KEY = "documents/" + "ab" * 32


def _pair(s):
    """Survivor in dossier A; the copy in A and in B, where the survivor is not."""
    survivor, copy = register(s, KEY), register(s, KEY)
    s.flush()
    a, b = dossiers.ensure(s, "A"), dossiers.ensure(s, "B")
    dossiers.add(s, a.id, survivor.id, actor="t")
    dossiers.add(s, a.id, copy.id, actor="t")
    dossiers.add(s, b.id, copy.id, actor="t")
    s.commit()
    return survivor.id, copy.id, a.id, b.id


def _members(s, doc_id):
    return set(s.execute(select(DossierDocument.dossier_id)
                         .where(DossierDocument.document_id == doc_id)).scalars())


def test_a_copy_is_retired_with_its_history_and_its_dossiers_passed_on(session):
    survivor, copy, a, b = _pair(session)
    index = InMemoryIndex()
    index.index(str(survivor), "tekst", KEY)
    index.index(str(copy), "tekst", KEY)

    out = supersede(session, copy, survivor, actor="dedupe", index=index)
    session.commit()

    assert out == {"superseded": True, "moved": 1, "removed": 2, "index_entry": True}
    assert current_state(session, copy) == State.SUPERSEDED
    assert session.get(Document, copy).superseded_by == survivor
    assert _members(session, copy) == set()
    assert _members(session, survivor) == {a, b}          # B passed on, not lost
    assert [h.document_id for h in index.search("tekst")] == [str(survivor)]
    steps = [r.step for r in session.execute(
        select(AuditRecord).where(AuditRecord.document_id == copy)
        .order_by(AuditRecord.seq)).scalars()]
    assert steps[0] == "register" and steps[-1] == "supersede"
    assert steps.count("dossier_removed") == 2              # each removal recorded


def test_superseding_twice_is_a_no_op(session):
    survivor, copy, _, _ = _pair(session)
    supersede(session, copy, survivor, actor="dedupe")
    session.commit()
    assert supersede(session, copy, survivor, actor="dedupe")["superseded"] is False


def test_what_is_not_a_copy_is_refused(session):
    survivor, copy, _, _ = _pair(session)
    other = register(session, "documents/" + "cd" * 32)
    session.flush()
    with pytest.raises(SupersessionError, match="differ"):
        supersede(session, other.id, survivor, actor="dedupe")
    with pytest.raises(SupersessionError, match="itself"):
        supersede(session, survivor, survivor, actor="dedupe")
    supersede(session, copy, survivor, actor="dedupe")
    with pytest.raises(SupersessionError, match="survivor is itself superseded"):
        supersede(session, survivor, copy, actor="dedupe")


def test_the_pointer_is_set_once(session):
    survivor, copy, _, _ = _pair(session)
    supersede(session, copy, survivor, actor="dedupe")
    session.commit()
    with pytest.raises(DBAPIError, match="set once"):
        session.execute(text("UPDATE documents SET superseded_by = NULL WHERE id = :c"),
                        {"c": copy})
    session.rollback()


def test_a_retired_copy_cannot_join_a_dossier(session):
    survivor, copy, a, _ = _pair(session)
    supersede(session, copy, survivor, actor="dedupe")
    session.commit()
    with pytest.raises(dossiers.DossierError, match="superseded"):
        dossiers.add(session, a, copy, actor="t")


def test_a_retired_copy_is_not_an_orphan(session):
    survivor, copy, _, _ = _pair(session)
    supersede(session, copy, survivor, actor="dedupe")
    session.commit()
    assert copy not in {d.id for d in orphans(session)}


def test_the_same_bytes_arriving_again_find_the_survivor(session, mem_store,
                                                         born_digital_pii_pdf):
    """The retired copy is the OLDER row here on purpose: "the first row with
    this key" would find it, and only "the live one" finds the survivor."""
    older = ingest(session, mem_store, born_digital_pii_pdf)
    survivor = register(session, older.object_key)
    session.flush()
    supersede(session, older.id, survivor.id, actor="dedupe")
    session.commit()
    # Superseding UPDATEs the older row, which moves it to the end of the heap,
    # so an unordered "first row" would find the survivor by luck. Touch the
    # survivor last so the retired copy is what a careless lookup finds first.
    session.execute(text("UPDATE documents SET filename = 'x' WHERE id = :i"),
                    {"i": survivor.id})
    session.commit()
    again = ingest(session, mem_store, born_digital_pii_pdf, dossier="C")
    assert again.id == survivor.id
    assert live_document_for(session, older.object_key).id == survivor.id


def test_a_retired_copy_answers_for_itself(session_factory):
    with session_factory() as s:
        survivor, copy, _, _ = _pair(s)
        supersede(s, copy, survivor, actor="dedupe")
        s.commit()
    c = TestClient(create_app(session_factory=session_factory))
    body = c.get(f"/documents/{copy}/state").json()
    assert body == {"document_id": str(copy), "state": "superseded",
                    "superseded_by": str(survivor)}
    assert "superseded_by" not in c.get(f"/documents/{survivor}/state").json()


def test_the_console_lists_live_documents_only(session_factory):
    with session_factory() as s:
        survivor = register(s, KEY, filename="levend.pdf")
        copy = register(s, KEY, filename="kopie.pdf")
        s.flush()
        supersede(s, copy.id, survivor.id, actor="dedupe")
        s.commit()
    c = TestClient(create_app(session_factory=session_factory,
                              api_keys={"s3cret": "mark"}),
                   follow_redirects=False, base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    page = c.get("/console").text
    assert "levend.pdf" in page and "kopie.pdf" not in page
