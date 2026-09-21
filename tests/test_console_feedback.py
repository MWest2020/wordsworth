# SPDX-License-Identifier: MIT
"""Detectie corrigeren vanaf het scherm (overdetectie).

Mark, 2026-09-20: *"wat belangrijker is: gebruiksgemak om aan te geven of de PII
juist/niet juist is. Daar ligt de echte waarde."*

Het eindpunt bestond al en was alleen met curl te bereiken. Wat ontbrak was de
weg ernaartoe. Deze tests gaan over die weg — en vooral over wat er NIET
meegaat: er is geen vrij tekstveld, want dat zou klare PII het append-only spoor
in dragen.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.models import AuditRecord, Document, DocumentText

KEYS = {"s3cret": "mark"}
KOP = {"x-api-key": "s3cret"}
TEKST = ("Geachte heer, de aanvraag van [PERSON:3fa9c2d1] voor het perceel aan "
         "de [LOCATION:11223344] is ontvangen.")


def _doc(session_factory):
    from wordsworth import audit
    from wordsworth.states import State

    with session_factory() as s:
        doc = Document(object_key="documents/feedback", filename="brief.pdf")
        s.add(doc)
        s.flush()
        s.merge(DocumentText(document_id=doc.id, anonymized_text=TEKST))
        audit.append(s, document_id=doc.id, from_state=None,
                     to_state=State.INDEXED.value, step="index", payload={})
        s.commit()
        return doc.id


def _client(session_factory):
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                   base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    return c


def test_every_token_is_clickable_and_says_what_it_is_for(session_factory):
    """Zonder aanwijzing is een klikbaar token een verborgen functie."""
    doc_id = _doc(session_factory)
    pagina = _client(session_factory).get(f"/console/documents/{doc_id}").text
    assert 'data-token="[PERSON:3fa9c2d1]"' in pagina
    assert 'data-type="PERSON"' in pagina
    assert "klik als dit geen PERSON is" in pagina
    assert "Klopt er iets niet?" in pagina


def test_the_missed_form_offers_the_types_the_system_knows(session_factory):
    """Uit het typeregister, niet uit een lijstje in de template: anders meldt
    iemand straks een type dat het systeem niet kent."""
    doc_id = _doc(session_factory)
    pagina = _client(session_factory).get(f"/console/documents/{doc_id}").text
    for t in ("PERSON", "BSN", "GEZONDHEID"):
        assert f'<option value="{t}">' in pagina


def test_the_page_says_no_value_ever_travels(session_factory):
    """De belangrijkste zin op deze pagina. Wie meldt moet weten dat hij geen
    waarde deelt, anders gaat hij er zelf een in een veld typen dat er niet is."""
    doc_id = _doc(session_factory)
    pagina = _client(session_factory).get(f"/console/documents/{doc_id}").text
    assert "Nooit een waarde" in pagina
    assert "geen vrij tekstveld" in pagina


def test_there_is_no_free_text_field_on_the_form(session_factory):
    """En het staat er niet alleen: het IS er niet."""
    doc_id = _doc(session_factory)
    pagina = _client(session_factory).get(f"/console/documents/{doc_id}").text
    formulier = pagina.split('id="fbmis"')[1].split("</form>")[0]
    assert "<textarea" not in formulier
    assert 'type="text"' not in formulier


def test_reporting_a_false_positive_lands_in_the_trail(session_factory):
    from sqlalchemy import select

    doc_id = _doc(session_factory)
    c = _client(session_factory)
    r = c.post(f"/documents/{doc_id}/feedback", headers=KOP,
               json={"kind": "fp", "type": "PERSON", "token": "[PERSON:3fa9c2d1]"})
    assert r.status_code == 201

    with session_factory() as s:
        payload = s.execute(
            select(AuditRecord.payload)
            .where(AuditRecord.document_id == doc_id,
                   AuditRecord.step == "detection_feedback")
            .order_by(AuditRecord.seq.desc()).limit(1)).scalar_one()
    assert payload["kind"] == "fp" and payload["type"] == "PERSON"
    assert payload["token"] == "[PERSON:3fa9c2d1]"
    assert payload["caller"] == "mark", "wie het meldde hoort erbij"
    # En geen enkele klare waarde.
    assert "perceel" not in str(payload) and "Geachte" not in str(payload)


def test_a_value_is_refused_where_a_token_belongs(session_factory):
    """De rem op het eindpunt zelf. Zonder deze zou een client de sleutel van
    het hele ding -- geen klare waarde in het spoor -- kunnen omzeilen."""
    doc_id = _doc(session_factory)
    r = _client(session_factory).post(
        f"/documents/{doc_id}/feedback", headers=KOP,
        json={"kind": "fp", "type": "PERSON", "token": "Jan Jansen"})
    assert r.status_code == 422


def test_a_miss_needs_no_token(session_factory):
    """Een gemiste waarde heeft per definitie geen token. Het type is alles wat
    er te zeggen valt zonder een waarde te noemen."""
    doc_id = _doc(session_factory)
    r = _client(session_factory).post(
        f"/documents/{doc_id}/feedback", headers=KOP,
        json={"kind": "fn", "type": "ADRES"})
    assert r.status_code == 201
    assert r.json()["recorded"]["token"] is None
