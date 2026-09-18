# SPDX-License-Identifier: MIT
"""De dossiergrens zoals de ÉCHTE zoekdriver hem stelt (codereview 18-09).

Elke scoping-test tot nu toe draaide op `InMemoryIndex` — een aparte
implementatie, voor de tests geschreven. Die bewijst het model en niet de
belofte: wat in productie de grens afdwingt is `_scoped()` plus de querybody die
`OpenSearchIndex` verstuurt, en daar raakte geen enkele test aan.

Dat is dezelfde fout die de mapping-bug van dezelfde dag kon laten ontstaan: de
tests maken de index vers aan, productie niet, en het verschil kwam pas boven
toen een gescopete zoekopdracht daar nul teruggaf.

Deze tests kijken naar wat er de deur uitgaat, met een nepclient. Ze hebben geen
draaiende OpenSearch nodig en vervangen die ook niet — wat ze bewaken is de
querybody, want dat is het stuk dat fout kan zonder dat iets het zegt.
"""

from wordsworth.opensearch_index import OpenSearchIndex, _scoped


class Vangt:
    """Onthoudt de querybody in plaats van hem te versturen."""

    def __init__(self, hits=()):
        self.bodies = []
        self._hits = list(hits)

    def search(self, index, body):
        self.bodies.append(body)
        return {"hits": {"hits": self._hits}}

    def mget(self, body, index, _source=None):
        return {"docs": []}


def _index(hits=()):
    return OpenSearchIndex(Vangt(hits), "ww", 64)


def test_without_a_scope_no_filter_is_sent():
    """'alle dossiers' is een expliciete keuze en mag geen lege filter worden —
    een `terms` met nul waarden matcht niets, en dat zou 'alles' stil in 'niets'
    veranderen."""
    idx = _index()
    idx.search("vergunning")
    body = idx._client.bodies[0]
    assert "bool" not in body["query"]
    assert "filter" not in str(body["query"])


def test_a_scope_becomes_a_terms_filter_on_the_keyword_field():
    idx = _index()
    idx.search("vergunning", only=["d1", "d2"])
    q = idx._client.bodies[0]["query"]
    assert q["bool"]["filter"] == [{"terms": {"dossiers": ["d1", "d2"]}}]
    assert q["bool"]["must"], "de eigenlijke zoekvraag blijft staan"


def test_the_filter_does_not_touch_the_score():
    """Een filter en geen must: een treffer hoort even hoog te staan of je nu
    één dossier doorzocht of alle. Zat hij in `must`, dan telde de dossiernaam
    mee in de relevantie."""
    q = _scoped({"match": {"text": "x"}}, ["d1"])
    assert "filter" in q["bool"] and len(q["bool"]["must"]) == 1
    assert q["bool"]["must"][0] == {"match": {"text": "x"}}


def test_an_empty_scope_list_still_filters_to_nothing():
    """Een lege lijst is niet hetzelfde als None. None betekent 'alle dossiers';
    een lege lijst betekent 'geen enkel dossier', en dat hoort niets terug te
    geven in plaats van alles."""
    q = _scoped({"match": {"text": "x"}}, [])
    assert q["bool"]["filter"] == [{"terms": {"dossiers": []}}]


def test_the_hybrid_path_scopes_both_halves():
    """De kNN-helft moet dezelfde grens krijgen als de lexicale. Anders levert
    een gescopete hybride zoekopdracht kandidaten uit vreemde dossiers aan, en
    die vallen dan pas weg — of niet."""
    idx = _index()
    idx.hybrid_search("vergunning", [0.1] * 64, recall=10, only=["d1"])
    assert len(idx._client.bodies) == 2
    for body in idx._client.bodies:
        assert body["query"]["bool"]["filter"] == [
            {"terms": {"dossiers": ["d1"]}}], body


def test_the_knn_filter_placement_is_recorded_as_unverified():
    """De codereview vroeg zich af of het filter buiten de `knn`-clause als
    NA-filter werkt: knn levert dan de globale top-k en het filter gooit de rest
    weg, zodat een klein dossier in een groot corpus stil te weinig
    vectorkandidaten krijgt.

    Gemeten op 18-09 tegen de draaiende index: beide plaatsingen gaven hetzelfde
    (100 treffers in een bestaand dossier, 0 in een onbestaand). Dat is GEEN
    weerlegging — op dat moment zaten alle herstelde vectoren in één groot
    dossier, dus het geval waar het om gaat was niet te maken.

    Deze test legt alleen de vorm vast die nu draait, zodat een wijziging eraan
    opvalt. De meting zelf hoort opnieuw zodra de herberekening klaar is en er
    vectoren in een klein dossier staan.
    """
    q = _scoped({"knn": {"vector": {"vector": [0.1], "k": 10}}}, ["d1"])
    assert q["bool"]["must"][0]["knn"]["vector"]["k"] == 10
    assert "filter" not in q["bool"]["must"][0]["knn"]["vector"]


def test_the_mapping_declares_dossiers_as_keyword():
    """Een `text`-veld wordt geanalyseerd, en dan matcht een `terms` op een uuid
    niets — zonder fout. Precies wat er op 18-09 in productie gebeurde omdat het
    veld daar dynamisch was aangemaakt."""
    from wordsworth.opensearch_index import _mapping

    assert _mapping(64)["mappings"]["properties"]["dossiers"] == {"type": "keyword"}
