# SPDX-License-Identifier: MIT
"""De onderwerpenpagina in de console (onderwerpen).

Getoetst op wat een lezer ziet, want dat is waar deze pagina voor is: de winst
zit niet in een getal maar in dat een mens ziet waar een dossier over gaat
voordat hij zijn eerste zoekterm verzint.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.dossiers import add, ensure
from wordsworth.models import DocumentText
from wordsworth.pipeline import register
from wordsworth.search_index import InMemoryIndex


def _corpus(session_factory, index, naam="gooise-meren-woo-2022"):
    with session_factory() as s:
        d = ensure(s, naam)
        s.flush()
        for kant, woord, vec in (("v", "vergunning kap boom", [1.0, 0.0]),
                                 ("s", "subsidie cultuur regeling", [0.0, 1.0])):
            for i in range(4):
                # Via register: een document zonder auditrecord bestaat in
                # productie niet, en sinds dossier-audit hangt er een
                # lidmaatschapsrecord aan diezelfde keten.
                doc = register(s, f"documents/{kant}{i}", filename=f"{kant}{i}.pdf")
                add(s, d.id, doc.id, actor="test")
                tekst = f"gemeente {woord} {i}"
                s.merge(DocumentText(document_id=doc.id, anonymized_text=tekst))
                index.index(str(doc.id), tekst, f"documents/{kant}{i}",
                            vector=vec, dossiers=[str(d.id)])
        s.commit()
    return naam


KEYS = {"s3cret": "mark"}


def _client(session_factory, index):
    """Ingelogd, want de console hangt achter de sleutel. De koude kant (zonder
    sleutel) staat in `test_console_demo.py` en geldt ook voor deze pagina's."""
    client = TestClient(create_app(session_factory=session_factory,
                                   api_keys=KEYS, search_index=index),
                        base_url="https://testserver")
    client.post("/console/login", data={"key": "s3cret"})
    return client


def test_the_page_says_it_has_not_been_computed_yet(session_factory):
    index = InMemoryIndex()
    naam = _corpus(session_factory, index)
    r = _client(session_factory, index).get(f"/console/topics?dossier={naam}")
    assert r.status_code == 200
    assert "nog niet berekend" in r.text
    assert "Nog geen onderwerpen" in r.text


def test_computing_shows_the_groups_with_their_denominator(session_factory):
    index = InMemoryIndex()
    naam = _corpus(session_factory, index)
    r = _client(session_factory, index).post("/console/topics",
                                             data={"dossier": naam})
    assert r.status_code == 200
    assert "vergunning" in r.text and "subsidie" in r.text
    # De noemer hoort op het scherm: zonder die drie getallen leest een lijst
    # van twee onderwerpen als een uitspraak over het hele dossier.
    assert "8" in r.text and "zonder onderwerp" in r.text
    assert "berekend" in r.text


def test_an_unknown_dossier_says_so_instead_of_showing_nothing(session_factory):
    index = InMemoryIndex()
    _corpus(session_factory, index)
    r = _client(session_factory, index).get("/console/topics?dossier=bestaat-niet")
    assert "bestaat niet" in r.text
    assert "Nog geen onderwerpen" not in r.text


def test_the_topic_link_searches_inside_that_topic(session_factory):
    """Doorklikken is de hele bedoeling: van 'waar gaat dit over' naar 'zoek
    daarbinnen'. De zoekpagina moet dan ook zéggen dat hij versmald is."""
    index = InMemoryIndex()
    naam = _corpus(session_factory, index)
    client = _client(session_factory, index)
    client.post("/console/topics", data={"dossier": naam})
    topics = client.get(f"/dossiers/{_dossier_id(session_factory, naam)}/topics",
                        headers={"x-api-key": "s3cret"}).json()["topics"]
    topic = topics[0]

    r = client.get("/console/search", params={"q": "gemeente", "dossier": naam,
                                              "topic": topic["id"]})
    assert r.status_code == 200
    assert "binnen het onderwerp" in r.text
    assert topic["name"] in r.text
    assert "Zoek in het hele dossier" in r.text, "er moet een weg terug zijn"
    # Precies de documenten van dat onderwerp, niet het hele dossier.
    assert r.text.count("/console/documents/") == topic["document_count"]


def test_an_unknown_topic_does_not_pretend_to_be_one(session_factory):
    from uuid import uuid4

    index = InMemoryIndex()
    naam = _corpus(session_factory, index)
    r = _client(session_factory, index).get(
        "/console/search", params={"q": "gemeente", "dossier": naam,
                                   "topic": str(uuid4())})
    assert "onbekend onderwerp" in r.text


def _dossier_id(session_factory, naam):
    from sqlalchemy import select

    from wordsworth.models import Dossier
    with session_factory() as s:
        return s.execute(select(Dossier.id).where(Dossier.name == naam)).scalar_one()
