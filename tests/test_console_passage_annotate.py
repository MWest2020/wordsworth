# SPDX-License-Identifier: MIT
"""`console_passage.annotate`: what can go wrong costs the explanation of one
hit, or of the page, and never the page itself (search-matching-passage)."""
import logging

from wordsworth.console_passage import MAX_PASSAGES, MEANING, annotate
from wordsworth.passages import split_spans
from wordsworth.search_index import InMemoryIndex

TEXT = "De aanvraag voor de dakkapel is geweigerd."


class Embedder:
    def __init__(self, blips=0):
        self.blips = blips

    def embed(self, texts):
        if self.blips:
            self.blips -= 1
            raise ConnectionError("ollama blip")
        return [[1.0, 0.0] for _ in texts]


class Index(InMemoryIndex):
    def __init__(self, vectors):
        super().__init__()
        self.vectors, self.asked = vectors, []

    def passages_of(self, ids):
        self.asked.append(list(ids))
        return {i: self.vectors[i] for i in ids if i in self.vectors}


def _hits(*ids):
    return [{"id": i} for i in ids]


def test_one_malformed_vector_costs_one_hit(caplog):
    index = Index({"goed": [[1.0, 0.0]], "kapot": [[1.0, None]], "leeg": [None]})
    hits = _hits("goed", "kapot", "leeg")
    with caplog.at_level(logging.WARNING, logger="wordsworth.search"):
        assert annotate(index, Embedder(), "dakkapel", hits, [TEXT] * 3) is False
    assert hits[0]["passage"]["words"] == ["dakkapel"]
    assert "passage" not in hits[1] and "passage" not in hits[2]
    assert "2 hit(s): malformed" in caplog.text


def test_another_dimension_is_one_warning_per_request(caplog):
    index = Index({"a": [[1.0, 0.0, 0.0]], "b": [[0.0, 1.0, 0.0]]})
    hits = _hits("a", "b")
    with caplog.at_level(logging.WARNING, logger="wordsworth.search"):
        annotate(index, Embedder(), "dakkapel", hits, [TEXT] * 2)
    warned = [r for r in caplog.records if "another dimension" in r.getMessage()]
    assert len(warned) == 1 and "2 hit(s)" in warned[0].getMessage()
    assert not any("passage" in h for h in hits)


def test_a_document_over_the_passage_cap_is_not_read():
    big = " ".join(f"w{i}" for i in range(30200))
    edge = " ".join(f"w{i}" for i in range(30050))
    assert len(split_spans(big)) == MAX_PASSAGES + 1
    assert len(split_spans(edge)) == MAX_PASSAGES
    index = Index({"edge": [[0.0, 1.0]] * MAX_PASSAGES})
    hits = _hits("big", "edge")
    assert annotate(index, Embedder(), "w5", hits, [big, edge]) is False
    assert index.asked == [["edge"]]
    assert "passage" not in hits[0] and "reden" not in hits[0]
    assert hits[1]["passage"]["span"] == split_spans(edge)[0]


def test_the_second_embedding_retries_a_blip_as_hybrid_does(monkeypatch):
    monkeypatch.setenv("WORDSWORTH_RETRY_BASE_DELAY", "0")
    hits = _hits("a")
    annotate(Index({"a": [[1.0, 0.0]]}), Embedder(blips=1), "Redenen?", hits, [TEXT])
    assert hits[0]["reden"] == MEANING
