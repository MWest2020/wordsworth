# SPDX-License-Identifier: MIT
"""Alleen herwerken wat nog niet onder de huidige lijsten is verwerkt.

Op 2026-09-20 liep een reprocess van 770 documenten veertien uur. Hij moest
onderbroken worden (de VM's gingen om), en zonder deze optie had de vervolgrun
alles overgedaan — inclusief de 200 die al af waren.

"Al bijgewerkt" is hier een **feit uit het auditspoor**, geen tijdstempel die
iemand moet onthouden: de lijst-hash staat in elk de-identificatie-record, dus
veranderen de lijsten, dan is elk document dat nog de oude hash draagt
achterstallig.
"""
from __future__ import annotations

import json

from wordsworth import audit
from wordsworth.models import Document
from wordsworth.pipeline import lists_hash_of
from wordsworth.states import State


def _doc(session, hash_=None, stap="anonymize"):
    doc = Document(object_key=f"documents/{id(session)}-{hash_}")
    session.add(doc)
    session.flush()
    audit.append(session, document_id=doc.id, from_state=None,
                 to_state=State.INDEXED.value, step=stap,
                 payload={"lists_hash": hash_})
    session.flush()
    return doc.id


def test_the_trail_says_under_which_lists_a_document_was_processed(session_factory):
    with session_factory() as s:
        doc_id = _doc(s, "abc123")
        assert lists_hash_of(s, doc_id) == "abc123"


def test_the_most_recent_run_wins(session_factory):
    """Een document dat opnieuw is verwerkt draagt de nieuwe hash, niet de
    oude."""
    with session_factory() as s:
        doc_id = _doc(s, "oud")
        audit.append(s, document_id=doc_id, from_state=State.INDEXED.value,
                     to_state=State.INDEXED.value, step="reanonymize",
                     payload={"lists_hash": "nieuw", "reanonymized": True})
        s.flush()
        assert lists_hash_of(s, doc_id) == "nieuw"


def test_a_document_never_processed_under_lists_counts_as_outdated(session_factory):
    """None telt als achterstallig zodra er lijsten zijn: liever een keer te
    veel werk dan een document dat stil de oude regels blijft dragen."""
    with session_factory() as s:
        doc_id = _doc(s, None)
        assert lists_hash_of(s, doc_id) is None


def test_other_audit_steps_do_not_answer_this_question(session_factory):
    """Alleen de de-identificatie zegt onder welke lijsten er gewerkt is. Een
    onthulling of een dossierwijziging zegt daar niets over, en zou de laatste
    echte waarde verbergen als hij meetelde."""
    with session_factory() as s:
        doc_id = _doc(s, "abc123")
        audit.append(s, document_id=doc_id, from_state=State.INDEXED.value,
                     to_state=State.INDEXED.value, step="deanonymize",
                     payload={"types": []})
        s.flush()
        assert lists_hash_of(s, doc_id) == "abc123"


def test_reprocess_skips_what_is_already_current(session_factory, tmp_path,
                                                 mem_store, mem_index,
                                                 fake_embedder, monkeypatch):
    """De hele reden dat dit bestaat: een onderbroken run mag niet betekenen
    dat de volgende alles overdoet."""
    from fastapi.testclient import TestClient

    from wordsworth.api import create_app
    from wordsworth.detection_lists import DetectionLists

    (tmp_path / "allow.json").write_text(json.dumps(
        {"LOCATION": [{"patroon": "(?i)^locatie$", "reden": "test"}]}),
        encoding="utf-8")
    huidig = DetectionLists.load(tmp_path).hash

    with session_factory() as s:
        bij = _doc(s, huidig)        # al onder de huidige lijsten verwerkt
        achter = _doc(s, "oude-hash")
        s.commit()

    # Het eindpunt leest de lijsten uit de instellingen, net als `serve.py`
    # dat doet voor de anonymizer -- één bron, geen tweede.
    monkeypatch.setenv("WORDSWORTH_DETECTION_LISTS", str(tmp_path))

    # /reprocess vraagt een anonymizer_factory. Wat hij doet maakt hier niet
    # uit -- de vraag is WELKE documenten hij te zien krijgt, en de poging zelf
    # mag mislukken.
    from wordsworth.mapping_store import PostgresMappingStore
    from wordsworth.keys import InMemoryKeyProvider
    from wordsworth.pseudonymizer import ReversibleAnonymizer

    kp = InMemoryKeyProvider()

    app = create_app(
        session_factory=session_factory, store=mem_store,
        search_index=mem_index, embedder=fake_embedder,
        anonymizer_factory=lambda ses: ReversibleAnonymizer(
            kp, PostgresMappingStore(ses), detect=lambda t: []))
    c = TestClient(app)
    r = c.post("/reprocess", json={"only_outdated": True})
    assert r.status_code == 200, r.text
    # Het achterstallige document is geprobeerd, het bijgewerkte niet.
    assert r.json()["total"] == 1, f"verwacht alleen {achter}, niet {bij}"

    # En zonder de vlag komen ze er allebei in.
    alles = c.post("/reprocess", json={}).json()
    assert alles["total"] == 2


def test_a_failure_leaves_a_trace_in_the_trail(session_factory, mem_store,
                                               mem_index, fake_embedder):
    """Dit is waarom de lus één plek heeft.

    Op 2026-09-20 bouwde ik hem na in een Job en liet deze registratie weg.
    Gevolg: een run van 250 documenten liet geen enkel spoor na van wat er
    misging, en achteraf was niet vast te stellen wát er mis was — precies de
    situatie waarvoor iemand in september `reprocess_failed` had toegevoegd.
    """
    from sqlalchemy import select

    from wordsworth import reprocess as backfill
    from wordsworth.models import AuditRecord

    class Weigert:
        def anonymize(self, text):
            raise RuntimeError("de motor doet het niet")

    with session_factory() as s:
        doc_id = _doc(s, "oude-hash")
        doc = s.get(Document, doc_id)
        # Het bronbestand moet er zijn, anders faalt hij al bij het ophalen en
        # toetst deze test iets anders dan hij beweert. (Zo kwam ik er overigens
        # achter hoe een ontbrekend object eruitziet: ObjectStoreError <- KeyError.)
        mem_store.put(doc.object_key, b"%PDF-1.4 nep")
        s.commit()

    counts, problems = backfill.run(
        session_factory, [doc_id],
        make_anonymizer=lambda ses, domain: Weigert(),
        store=mem_store, search_index=mem_index, embedder=fake_embedder)

    assert counts["failed"] + counts["retryable"] == 1
    assert problems, "de oorzaak hoort teruggegeven te worden"

    with session_factory() as s:
        payload = s.execute(
            select(AuditRecord.payload)
            .where(AuditRecord.document_id == doc_id,
                   AuditRecord.step == "reprocess_failed")
            .order_by(AuditRecord.seq.desc()).limit(1)).scalar_one_or_none()
    assert payload is not None, "de mislukking staat niet in het spoor"
    assert payload["error_class"], "de oorzaakketen hoort erin te staan"
    assert "transient" in payload
    # En geen tekst uit het document.
    assert "de motor doet het niet" not in str(payload)
