# SPDX-License-Identifier: MIT
"""`SearchIndex.passages_of` on both drivers, without a cluster.

The OpenSearch half runs against a fake client here; the real ``mget`` is in
`test_opensearch_passages_of.py`, which runs in CI.
"""
import json
import logging

import pytest

from wordsworth.opensearch_index import OpenSearchIndex
from wordsworth.search_index import InMemoryIndex, SearchUnavailable

IDS = [f"d{i}" for i in range(11)]


def _memory():
    index = InMemoryIndex()
    index.index("met", "tekst met passages", "k1", passages=[[1.0, 0.0], [0.0, 1.0]])
    index.index("zonder", "tekst zonder passages", "k2")
    return index


class FakeClient:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def mget(self, body, index, _source):
        self.calls.append((body["ids"], _source))
        if self.fail:
            raise self.fail
        return {"docs": [
            {"_id": "met", "found": True,
             "_source": {"passages": [{"vector": [1.0, 0.0]}, {"vector": [0.0, 1.0]}]}},
            {"_id": "zonder", "found": True, "_source": {}},
            {"_id": "weg", "found": False},
        ]}


class TestInMemory:
    def test_it_returns_the_vectors_of_the_asked_ids(self):
        found = _memory().passages_of(["met", "zonder", "weg"])
        assert found["met"] == [[1.0, 0.0], [0.0, 1.0]]
        assert found.get("zonder", []) == [] and found.get("weg", []) == []

    def test_more_than_ten_ids_is_refused(self):
        with pytest.raises(ValueError, match="at most 10"):
            _memory().passages_of(IDS)

    def test_ten_ids_are_fine(self):
        assert _memory().passages_of(IDS[:10]) == {}


class TestOpenSearchDriver:
    def test_one_mget_for_the_passage_vectors_only(self):
        client = FakeClient()
        found = OpenSearchIndex(client, "i", dim=2).passages_of(["met", "zonder", "weg"])
        assert client.calls == [(["met", "zonder", "weg"], ["passages.vector"])]
        assert found["met"] == [[1.0, 0.0], [0.0, 1.0]]
        assert found.get("zonder", []) == [] and "weg" not in found

    def test_more_than_ten_ids_is_refused_before_the_read(self):
        client = FakeClient()
        with pytest.raises(ValueError, match="at most 10"):
            OpenSearchIndex(client, "i", dim=2).passages_of(IDS)
        assert client.calls == []

    def test_a_transport_failure_is_search_unavailable(self):
        index = OpenSearchIndex(FakeClient(fail=ConnectionError("refused")), "i", dim=2)
        with pytest.raises(SearchUnavailable):
            index.passages_of(["met"])

    def test_a_rejected_read_stays_its_own_error(self):
        index = OpenSearchIndex(FakeClient(fail=KeyError("docs")), "i", dim=2)
        with pytest.raises(KeyError):
            index.passages_of(["met"])


def test_one_log_line_with_counts_and_no_id(caplog):
    with caplog.at_level(logging.INFO, logger="wordsworth.search"):
        _memory().passages_of(["met", "zonder"])
        OpenSearchIndex(FakeClient(), "i", dim=2).passages_of(["met", "zonder", "weg"])
    lines = [json.loads(r.getMessage()) for r in caplog.records
             if r.name == "wordsworth.search"]
    assert [(r["driver"], r["ids"], r["passages"]) for r in lines] == [
        ("memory", 2, 2), ("opensearch", 3, 2)]
    assert all(isinstance(r["ms"], float) for r in lines)
    assert "met" not in caplog.text and "zonder" not in caplog.text
    assert "tekst" not in caplog.text
