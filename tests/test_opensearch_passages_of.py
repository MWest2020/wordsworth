# SPDX-License-Identifier: MIT
"""`OpenSearchIndex.passages_of` against a real cluster. Skips without one.

Runs in CI (the `ci` workflow has an OpenSearch 2 service). It proves the
``mget`` with ``_source=["passages.vector"]`` returns the nested vectors in the
order they were written -- the order `split_spans` gives -- on a small index.
The real index is first exercised at the demo rehearsal.
"""
import pytest

from wordsworth.config import settings
from wordsworth.opensearch_index import OpenSearchIndex
from wordsworth.search_index import SearchUnavailable


@pytest.fixture
def os_index():
    pytest.importorskip("opensearchpy")
    from opensearchpy import OpenSearch

    client = OpenSearch(hosts=[settings.opensearch_url])
    try:
        client.info()
    except Exception:
        pytest.skip("OpenSearch not reachable")
    name = "wordsworth_test_passages_of"
    client.indices.delete(index=name, ignore=[404])
    index = OpenSearchIndex(client, name, dim=4)
    index.ensure_ready()
    yield index
    client.indices.delete(index=name, ignore=[404])


P = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]]


def test_the_passage_vectors_come_back_in_order(os_index):
    os_index.index("lang", "een lange tekst", "k1", vector=[1, 1, 1, 1], passages=P)
    os_index.index("kort", "een korte tekst", "k2", vector=[1, 0, 0, 1], passages=P[:1])
    os_index.index("leeg", "zonder passages", "k3", vector=[0, 0, 1, 1])
    found = os_index.passages_of(["lang", "kort", "leeg", "nooit-geindexeerd"])
    assert found["lang"] == P
    assert found["kort"] == P[:1]
    assert found.get("leeg", []) == []
    assert found.get("nooit-geindexeerd", []) == []


def test_more_than_ten_ids_is_refused(os_index):
    with pytest.raises(ValueError):
        os_index.passages_of([f"d{i}" for i in range(11)])


def test_an_unreachable_cluster_is_search_unavailable():
    pytest.importorskip("opensearchpy")
    from opensearchpy import OpenSearch

    # A port nothing listens on: the transport fails, the query is not at fault.
    client = OpenSearch(hosts=["http://127.0.0.1:9"], max_retries=0, timeout=2)
    with pytest.raises(SearchUnavailable):
        OpenSearchIndex(client, "wordsworth_test_passages_of", dim=4).passages_of(["x"])
