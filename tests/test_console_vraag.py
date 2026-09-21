# SPDX-License-Identifier: MIT
"""Een vraag stellen aan het corpus, niet een trefwoord typen.

Een vraag bevat zelden de woorden die in het antwoord staan. Met een embedder
wordt de vraag zélf geëmbed en doet `hybrid_search` het werk; zonder embedder
blijft het BM25 — en dan staat dát er ook bij, want stil terugvallen op iets
zwakkers laat iemand de magere uitslag aan het corpus wijten.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.dossiers import add, ensure
from wordsworth.models import Document, DocumentText
from wordsworth.search_index import InMemoryIndex

KEYS = {"s3cret": "mark"}


class Embedder:
    """Een vraag over weigeren ligt dicht bij het document dat weigert, ook al
    deelt hij er geen woord mee. Precies het geval dat BM25 mist."""

    def embed(self, teksten):
        uit = []
        for t in teksten:
            laag = t.lower()
            over_weigeren = any(w in laag for w in
                                ("geweigerd", "weiger", "afgewezen", "afkeuring"))
            uit.append([1.0, 0.0] if over_weigeren else [0.0, 1.0])
        return uit


def _corpus(session_factory, index):
    with session_factory() as s:
        d = ensure(s, "zaak")
        s.flush()
        stukken = {
            "weigering": "De aanvraag is afgewezen omdat de dakkapel niet voldoet.",
            "toekenning": "De vergunning voor de dakkapel is verleend.",
            "iets": "Een notulen over parkeren en fietsenstallingen.",
        }
        for naam, tekst in stukken.items():
            doc = Document(object_key=f"documents/{naam}", filename=f"{naam}.pdf")
            s.add(doc)
            s.flush()
            add(s, d.id, doc.id)
            s.merge(DocumentText(document_id=doc.id, anonymized_text=tekst))
            index.index(str(doc.id), tekst, f"documents/{naam}",
                        vector=Embedder().embed([tekst])[0], dossiers=[str(d.id)])
        s.commit()


def _client(session_factory, index, embedder=None):
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS,
                              search_index=index, embedder=embedder),
                   base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    return c


def test_a_question_finds_the_document_that_shares_no_word_with_it(session_factory):
    """De kern van "stel een vraag": "Waarom niet?" en "afgewezen" delen geen
    woord, en BM25 vindt het document dus niet."""
    index = InMemoryIndex()
    _corpus(session_factory, index)
    # Geen enkel woord uit deze vraag staat in enig document. Met "Waarom
    # niet?" zou BM25 toevallig raak schieten op het stopwoord "niet" -- dan
    # bewijst de test niets.
    vraag = {"q": "Redenen tot afkeuring?", "dossier": "zaak"}

    zonder = _client(session_factory, index).get("/console/search", params=vraag)
    assert "weigering" not in zonder.text, "BM25 zou dit niet moeten vinden"
    assert "lexicaal" in zonder.text

    met = _client(session_factory, index, Embedder()).get("/console/search",
                                                          params=vraag)
    assert "weigering" in met.text
    assert "semantisch + lexicaal" in met.text


def test_it_says_when_it_is_only_lexical(session_factory):
    """Stil terugvallen op iets zwakkers is erger dan het niet hebben: dan wijt
    iemand de magere uitslag aan het corpus."""
    index = InMemoryIndex()
    _corpus(session_factory, index)
    r = _client(session_factory, index).get(
        "/console/search", params={"q": "dakkapel", "dossier": "zaak"})
    assert "zonder embedder" in r.text
    assert "lexicale" in r.text


def test_the_scope_still_applies_to_a_question(session_factory):
    """Een vraag stellen mag de dossiergrens niet omzeilen."""
    index = InMemoryIndex()
    _corpus(session_factory, index)
    c = _client(session_factory, index, Embedder())
    assert "Kies eerst een dossier" in c.get(
        "/console/search", params={"q": "Waarom niet?"}).text
    assert "unknown dossier" in c.get(
        "/console/search", params={"q": "Waarom niet?", "dossier": "elders"}).text


def test_a_topic_still_narrows_a_question(session_factory):
    from wordsworth import topics as tp
    from wordsworth.models import Dossier
    from sqlalchemy import select

    index = InMemoryIndex()
    _corpus(session_factory, index)
    with session_factory() as s:
        d = s.execute(select(Dossier)).scalars().first()
        tp.compute(s, index, d.id, min_size=1)
        s.commit()
        onderwerp = tp.listing(s, d.id)[0]
        naam, tid = onderwerp.computed_name, str(onderwerp.id)
        aantal = onderwerp.document_count

    r = _client(session_factory, index, Embedder()).get(
        "/console/search", params={"q": "Waarom niet?", "dossier": "zaak",
                                   "topic": tid})
    assert "binnen het onderwerp" in r.text and naam in r.text
    assert r.text.count("/console/documents/") <= aantal
