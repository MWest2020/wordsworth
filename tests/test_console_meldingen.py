# SPDX-License-Identifier: MIT
"""Het meldingenscherm (overdetectie).

Losse meldingen zijn geen signaal; "vijf mensen vonden dit token onterecht" is
er wel een. Dit scherm maakt dat zichtbaar — en toont **geen waarden**, want een
overzicht dat die er "even" bij zet is de tweede deur met het grootste bereik.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.models import Document, DocumentText

KEYS = {"s3cret": "mark", "tweede": "anne", "derde": "sam"}
TEKST = "De aanvraag van [PERSON:3fa9c2d1] voor [LOCATION:11223344]."


def _doc(session_factory, naam="brief.pdf"):
    from wordsworth import audit
    from wordsworth.states import State

    with session_factory() as s:
        doc = Document(object_key=f"documents/{naam}", filename=naam)
        s.add(doc)
        s.flush()
        s.merge(DocumentText(document_id=doc.id, anonymized_text=TEKST))
        audit.append(s, document_id=doc.id, from_state=None,
                     to_state=State.INDEXED.value, step="index", payload={})
        s.commit()
        return doc.id


def _client(session_factory, sleutel="s3cret"):
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS),
                   base_url="https://testserver")
    c.post("/console/login", data={"key": sleutel})
    return c


def _meld(session_factory, doc_id, sleutel, **body):
    c = _client(session_factory, sleutel)
    r = c.post(f"/documents/{doc_id}/feedback", headers={"x-api-key": sleutel},
               json=body)
    assert r.status_code == 201, r.text
    return c


def test_it_says_so_when_nobody_has_reported_anything(session_factory):
    r = _client(session_factory).get("/console/feedback")
    assert r.status_code == 200
    assert "Nog niemand heeft een token onterecht genoemd" in r.text
    assert "Nog niemand heeft een gemiste waarde gemeld" in r.text


def test_three_people_on_one_token_count_as_three(session_factory):
    doc_id = _doc(session_factory)
    for sleutel in ("s3cret", "tweede", "derde"):
        _meld(session_factory, doc_id, sleutel, kind="fp", type="PERSON",
              token="[PERSON:3fa9c2d1]")
    pagina = _client(session_factory).get("/console/feedback").text
    assert "[PERSON:3fa9c2d1]" in pagina
    assert "mark" in pagina and "anne" in pagina and "sam" in pagina
    assert ">3<" in pagina, "het aantal MELDERS hoort het gewicht te zijn"


def test_one_person_clicking_ten_times_is_not_ten_people(session_factory):
    """Anders is het scherm te vullen door één iemand die doorklikt, en dan
    weegt een melding niets meer."""
    doc_id = _doc(session_factory)
    for _ in range(10):
        _meld(session_factory, doc_id, "s3cret", kind="fp", type="PERSON",
              token="[PERSON:3fa9c2d1]")
    pagina = _client(session_factory).get("/console/feedback").text
    assert ">1<" in pagina and ">10<" not in pagina


def test_the_heaviest_report_comes_first(session_factory):
    doc_id = _doc(session_factory)
    _meld(session_factory, doc_id, "s3cret", kind="fp", type="PERSON",
          token="[PERSON:3fa9c2d1]")
    for sleutel in ("s3cret", "tweede", "derde"):
        _meld(session_factory, doc_id, sleutel, kind="fp", type="LOCATION",
              token="[LOCATION:11223344]")
    pagina = _client(session_factory).get("/console/feedback").text
    assert pagina.index("[LOCATION:11223344]") < pagina.index("[PERSON:3fa9c2d1]")


def test_a_miss_is_shown_separately_and_has_no_token(session_factory):
    doc_id = _doc(session_factory)
    _meld(session_factory, doc_id, "s3cret", kind="fn", type="ADRES")
    pagina = _client(session_factory).get("/console/feedback").text
    gemist = pagina.split("Gemist")[1]
    assert "ADRES" in gemist


def test_it_links_through_to_the_document(session_factory):
    """Wegen kan alleen met het stuk erbij."""
    doc_id = _doc(session_factory, "besluit.pdf")
    _meld(session_factory, doc_id, "s3cret", kind="fp", type="PERSON",
          token="[PERSON:3fa9c2d1]")
    pagina = _client(session_factory).get("/console/feedback").text
    assert f"/console/documents/{doc_id}" in pagina
    assert "besluit.pdf" in pagina


def test_the_screen_never_shows_a_value(session_factory):
    """De belofte waar dit scherm op staat of valt. Een overzicht dat de waarde
    erbij zet is de tweede deur met het grootste bereik: hij toont ze allemaal
    tegelijk."""
    doc_id = _doc(session_factory)
    _meld(session_factory, doc_id, "s3cret", kind="fp", type="PERSON",
          token="[PERSON:3fa9c2d1]")
    pagina = _client(session_factory).get("/console/feedback").text
    # De opgeslagen tekst zelf komt hier niet voor -- alleen het token.
    assert "De aanvraag van" not in pagina
    assert "Hier staan geen waarden" in pagina


def test_it_is_behind_the_corpus_gate(session_factory):
    """Welke tokens in welke documenten staan is corpuskennis, ook zonder de
    waarden erbij."""
    app = create_app(session_factory=session_factory, api_keys=KEYS,
                     corpus_read_labels=["iemand-anders"])
    c = TestClient(app, base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    assert c.get("/console/feedback").status_code == 403
