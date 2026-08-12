"""Dutch analysis mapping + BM25 query shape — pure functions, offline."""
from __future__ import annotations

from wordsworth.opensearch_index import _bm25, _mapping


def test_mapping_has_dutch_analyzer_and_ngram_recall_field():
    m = _mapping(1024)
    analyzers = m["settings"]["analysis"]["analyzer"]
    assert {"nl_text", "nl_recall_index", "nl_recall_search"} <= set(analyzers)
    assert "asciifolding" in analyzers["nl_text"]["filter"]
    assert "nl_stemmer" in analyzers["nl_text"]["filter"]

    text = m["mappings"]["properties"]["text"]
    assert text["analyzer"] == "nl_text"
    recall = text["fields"]["recall"]
    assert recall["analyzer"] == "nl_recall_index"          # index n-grams
    assert recall["search_analyzer"] == "nl_recall_search"  # whole query terms
    assert m["mappings"]["properties"]["vector"]["dimension"] == 1024
    assert m["settings"]["index"]["knn"] is True


def test_bm25_queries_stemmed_and_recall_fields():
    q = _bm25("kosten")["multi_match"]
    assert q["query"] == "kosten"
    assert q["fields"] == ["text^3", "text.recall"]  # stemmed boosted, ngram recall
