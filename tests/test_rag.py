from wordsworth.embedder import DeterministicEmbedder
from wordsworth.generator import Answer, DeterministicGenerator, Source
from wordsworth.rag import NO_GROUNDED_ANSWER, ask
from wordsworth.search_index import InMemoryIndex


class RecordingGenerator:
    """Captures the sources it was handed and returns a scripted answer."""

    def __init__(self, answer: Answer):
        self.answer = answer
        self.seen: list[Source] = []

    def generate(self, query: str, sources: list[Source]) -> Answer:
        self.seen = list(sources)
        return self.answer


def _index(*docs: tuple[str, str]) -> tuple[InMemoryIndex, DeterministicEmbedder]:
    emb = DeterministicEmbedder(dim=64)
    idx = InMemoryIndex()
    for doc_id, text in docs:
        idx.index(doc_id, text, doc_id, vector=emb.embed([text])[0])
    return idx, emb


def test_sources_are_exactly_top_k_hybrid_hits():
    idx, emb = _index(
        ("relevant", "parkeervergunningen in de gemeente Haarlem"),
        ("off", "hondenbeleid en groenvoorziening"),
    )
    rec = RecordingGenerator(Answer("x", ["relevant"]))
    from wordsworth.hybrid import hybrid_search

    expected = [h.document_id for h in hybrid_search(idx, emb, "parkeervergunningen", size=1)]
    ask("parkeervergunningen", idx, emb, rec, k=1)
    assert [s.document_id for s in rec.seen] == expected


def test_sources_carry_deidentified_index_text():
    idx, emb = _index(("d1", "parkeervergunningen in Haarlem"))
    rec = RecordingGenerator(Answer("x", ["d1"]))
    ask("parkeervergunningen", idx, emb, rec, k=5)
    assert rec.seen[0].text == "parkeervergunningen in Haarlem"


def test_invented_citation_is_dropped():
    idx, emb = _index(("d1", "parkeervergunningen in Haarlem"))
    # Generator cites d1 (valid) plus an id that was never a source.
    gen = DeterministicGenerator(extra_citations=["ghost"])
    answer = ask("parkeervergunningen", idx, emb, gen, k=5)
    assert answer.citations == ["d1"]
    assert "ghost" not in answer.citations


def test_all_invalid_citations_yield_ungrounded_result():
    idx, emb = _index(("d1", "parkeervergunningen in Haarlem"))
    rec = RecordingGenerator(Answer("verzonnen proza", ["ghost1", "ghost2"]))
    answer = ask("parkeervergunningen", idx, emb, rec, k=5)
    assert answer.citations == []
    assert answer.text == NO_GROUNDED_ANSWER
    assert answer.text != "verzonnen proza"  # fabricated prose is not returned


def test_empty_index_yields_ungrounded_result():
    idx, emb = _index()  # no documents -> no sources -> nothing to cite
    gen = DeterministicGenerator()
    answer = ask("welke vraag dan ook", idx, emb, gen, k=5)
    assert answer.text == NO_GROUNDED_ANSWER
    assert answer.citations == []
