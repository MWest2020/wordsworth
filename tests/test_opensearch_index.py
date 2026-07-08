"""Integration tests for the real OpenSearch driver. Skip if no cluster."""
import pytest

from wordsworth.config import settings
from wordsworth.opensearch_index import OpenSearchIndex


@pytest.fixture
def os_index():
    pytest.importorskip("opensearchpy")
    from opensearchpy import OpenSearch

    client = OpenSearch(hosts=[settings.opensearch_url])
    try:
        client.info()
    except Exception:
        pytest.skip("OpenSearch not reachable")
    name = "wordsworth_test"
    client.indices.delete(index=name, ignore=[404])
    index = OpenSearchIndex(client, name)
    index.ensure_ready()
    yield index
    client.indices.delete(index=name, ignore=[404])


def test_index_and_keyword_search(os_index):
    os_index.index("d1", "de gemeente Haarlem besluit over parkeervergunningen", "k1")
    hits = os_index.search("gemeente")
    assert any(h.document_id == "d1" for h in hits)
    assert hits[0].score > 0
    assert hits[0].object_key == "k1"


def test_dutch_analyzer_stems(os_index):
    os_index.index("d1", "besluit over parkeervergunningen", "k")
    # Dutch analyzer stems the plural -> singular query still matches.
    assert any(h.document_id == "d1" for h in os_index.search("parkeervergunning"))


def test_ranking_order(os_index):
    os_index.index("weak", "iets heel anders over honden", "a")
    os_index.index("strong", "parkeren parkeren parkeren vergunning", "b")
    hits = os_index.search("parkeren vergunning")
    assert hits[0].document_id == "strong"


def test_reindex_does_not_duplicate(os_index):
    os_index.index("d1", "eerste versie", "k")
    os_index.index("d1", "tweede versie", "k")
    hits = os_index.search("versie")
    assert [h.document_id for h in hits].count("d1") == 1
