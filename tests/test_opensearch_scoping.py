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

from wordsworth.opensearch_index import (OpenSearchIndex, _bm25, _scoped,
                                         _scoped_knn)


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
    """Beide helften krijgen dezelfde grens, maar niet op dezelfde plek.

    De lexicale helft: een `bool.filter` naast de zoekvraag. De kNN-helft: het
    filter BINNEN de knn-clause, want daarbuiten is het een ná-filter. Zie
    `test_the_knn_filter_belongs_inside_the_clause` voor de meting."""
    idx = _index()
    idx.hybrid_search("vergunning", [0.1] * 64, recall=10, only=["d1"])
    assert len(idx._client.bodies) == 2
    lexicaal, vector = (b["query"] for b in idx._client.bodies)
    assert lexicaal["bool"]["filter"] == [{"terms": {"dossiers": ["d1"]}}]
    assert vector["knn"]["vector"]["filter"] == {"terms": {"dossiers": ["d1"]}}
    assert "bool" not in vector, "buiten de clause is het een ná-filter"


def test_the_knn_filter_belongs_inside_the_clause():
    """De vraag uit de codereview is op 18-09 gemeten en het antwoord is ja: het
    filter buiten de `knn`-clause werkt als ná-filter.

    Tegen de draaiende index, 770 documenten, zoekvector uit het grootste
    dossier (567 documenten), scope een dossier van 2 documenten:

        k=10  | filter buiten: 0 treffers | filter binnen: 2
        k=50  | filter buiten: 0 treffers | filter binnen: 2
        k=200 | filter buiten: 1 treffer  | filter binnen: 2

    De eerdere meting (alle vectoren in één groot dossier) gaf twee keer
    hetzelfde en leek een weerlegging. Dat was het niet: het geval waar het om
    gaat was toen niet te maken.

    Wat dit stil maakte: de hybride zoekopdracht gaf gewoon antwoorden, want de
    lexicale helft werkte. Alleen de vectorhelft droeg niets bij.
    """
    q = _scoped_knn([0.1], 10, ["d1"])
    assert q["knn"]["vector"]["filter"] == {"terms": {"dossiers": ["d1"]}}
    assert "bool" not in q


def test_without_a_scope_the_knn_clause_carries_no_filter():
    """'alle dossiers' hoort geen filter te krijgen. Een `terms` met nul
    waarden zou hier alles stil in niets veranderen."""
    q = _scoped_knn([0.1], 10, None)
    assert q == {"knn": {"vector": {"vector": [0.1], "k": 10}}}


def test_the_mapping_declares_dossiers_as_keyword():
    """Een `text`-veld wordt geanalyseerd, en dan matcht een `terms` op een uuid
    niets — zonder fout. Precies wat er op 18-09 in productie gebeurde omdat het
    veld daar dynamisch was aangemaakt."""
    from wordsworth.opensearch_index import _mapping

    assert _mapping(64)["mappings"]["properties"]["dossiers"] == {"type": "keyword"}


def test_a_topic_is_a_filter_and_never_a_must():
    """De belofte van `onderwerpen`: een onderwerp versmalt en herschikt niet.

    In `must` zou het onderwerp meetellen in de relevantie, en dan verschuift de
    volgorde om een reden die niemand aan de lezer kan uitleggen: dat een
    document op zijn buren lijkt.
    """
    idx = _index()
    idx.search("vergunning", only=["d1"], topic="t7")
    q = idx._client.bodies[0]["query"]
    assert q["bool"]["filter"] == [{"terms": {"dossiers": ["d1"]}},
                                   {"term": {"topics": "t7"}}]
    assert q["bool"]["must"] == [_bm25("vergunning")]


def test_the_topic_reaches_both_halves_of_the_hybrid_path():
    idx = _index()
    idx.hybrid_search("vergunning", [0.1] * 64, recall=10, only=["d1"], topic="t7")
    lexicaal, vector = (b["query"] for b in idx._client.bodies)
    assert {"term": {"topics": "t7"}} in lexicaal["bool"]["filter"]
    # Binnen de knn-clause, en met twee voorwaarden dus door een bool heen.
    binnen = vector["knn"]["vector"]["filter"]
    assert binnen["bool"]["filter"] == [{"terms": {"dossiers": ["d1"]}},
                                        {"term": {"topics": "t7"}}]


def test_a_topic_without_a_dossier_scope_still_filters():
    """'alle dossiers' plus één onderwerp is een geldige combinatie, en dan mag
    het onderwerp niet verdwijnen omdat de dossierlijst leeg is."""
    q = _scoped_knn([0.1], 10, None, "t7")
    assert q["knn"]["vector"]["filter"] == {"term": {"topics": "t7"}}


def test_the_mapping_declares_topics_as_keyword():
    from wordsworth.opensearch_index import _mapping

    assert _mapping(64)["mappings"]["properties"]["topics"] == {"type": "keyword"}
