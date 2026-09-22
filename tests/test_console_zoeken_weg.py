# SPDX-License-Identifier: MIT
"""Wat de console toont als de zoekindex wegvalt (hoge-beschikbaarheid 3.1).

Wordsworth draait op één OpenSearch-node, dus zoeken kán wegvallen — bij een
node-herstart is dat een paar minuten. Zolang dat zo is, hoort de console te
zeggen wát er weg is en wat er nog wél werkt.

Tot deze change deed hij dat niet. Elke fout uit de index werd hetzelfde:

    De zoekindex gaf een fout: ConnectionError

Dat is de klassenaam van een uitzondering, en het vertelt de lezer niet of hij
iets verkeerd deed of dat er een dienst omligt. Die twee vragen om verschillende
woorden: het ene kan hij oplossen, het andere niet.
"""
from fastapi.testclient import TestClient

from wordsworth.api import create_app
from wordsworth.dossiers import ensure
from wordsworth.search_index import InMemoryIndex, SearchUnavailable

KEYS = {"s3cret": "mark"}


class OnbereikbareIndex(InMemoryIndex):
    """Een index die niet te bereiken is: precies wat een node-herstart doet."""

    def search(self, *a, **kw):
        raise SearchUnavailable("search index unreachable: ConnectionError")

    def hybrid_search(self, *a, **kw):
        raise SearchUnavailable("search index unreachable: ConnectionError")

    def documents_in(self, *a, **kw):
        raise SearchUnavailable("search index unreachable: ConnectionError")


class StukkeIndex(InMemoryIndex):
    """Een index die er wél is en de vraag afwijst."""

    def search(self, *a, **kw):
        raise ValueError("malformed query")

    def hybrid_search(self, *a, **kw):
        raise ValueError("malformed query")


def _client(session_factory, index):
    c = TestClient(create_app(session_factory=session_factory, api_keys=KEYS,
                              search_index=index),
                   base_url="https://testserver")
    c.post("/console/login", data={"key": "s3cret"})
    return c


class TestZoekpagina:
    def test_een_onbereikbare_index_zegt_dat_het_niet_aan_de_vraag_ligt(
            self, session_factory):
        c = _client(session_factory, OnbereikbareIndex())
        body = c.get("/console/search", params={"q": "vergunning", "dossier": "alle"}).text

        assert "onbereikbaar" in body
        assert "niet aan je zoekopdracht" in body
        # en het zegt wat er nog wél kan, anders leest het als "alles stuk"
        assert "samenvattingen" in body or "Documenten" in body

    def test_een_afgewezen_vraag_krijgt_andere_woorden(self, session_factory):
        """De hele reden voor het onderscheid. Zou dit dezelfde tekst geven,
        dan is de melding waardeloos: de lezer weet nog steeds niet of hij iets
        moet veranderen."""
        c = _client(session_factory, StukkeIndex())
        body = c.get("/console/search", params={"q": "vergunning", "dossier": "alle"}).text

        assert "afgewezen" in body
        assert "onbereikbaar" not in body

    def test_de_pagina_blijft_een_pagina(self, session_factory):
        """Geen 500. Een storing in één functie hoort de console niet te slopen;
        anders is de melding er wel en ziet niemand hem."""
        c = _client(session_factory, OnbereikbareIndex())
        r = c.get("/console/search", params={"q": "vergunning", "dossier": "alle"})
        assert r.status_code == 200


class TestOnderwerpen:
    def test_berekenen_kan_niet_maar_het_eerdere_blijft_staan(self, session_factory):
        with session_factory() as s:
            ensure(s, "zaak")
            s.commit()
        c = _client(session_factory, OnbereikbareIndex())
        r = c.post("/console/topics", data={"dossier": "zaak"})

        assert r.status_code == 200
        assert "onbereikbaar" in r.text
        assert "blijft bruikbaar" in r.text


class TestDeNaad:
    def test_een_transportfout_wordt_searchunavailable(self):
        """De console mag niet hoeven weten welke driver eronder zit. De
        vertaling gebeurt in de driver, en een kapotte VERBINDING is iets anders
        dan een kapotte VRAAG."""
        from wordsworth.opensearch_index import _unreachable

        assert _unreachable(ConnectionError("refused"))
        assert _unreachable(TimeoutError())
        assert _unreachable(OSError("no route to host"))
        assert not _unreachable(ValueError("malformed query"))
        assert not _unreachable(KeyError("hits"))
