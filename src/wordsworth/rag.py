"""RAG flow: retrieve (deterministic) -> generate (local LLM) -> verify.

The rule is 'LLM advises, deterministic decides': hybrid retrieval chooses the
sources, the LLM only phrases an answer over them, and a deterministic guard
verifies every citation against the retrieved set. Citations the model invented
are dropped; an answer with no surviving citation is reported as ungrounded,
never returned as fabricated prose."""
from __future__ import annotations

from .embedder import Embedder
from .generator import Answer, Generator, Source
from .hybrid import hybrid_search
from .search_index import SearchIndex

NO_GROUNDED_ANSWER = "Geen onderbouwd antwoord: de bronnen dekken deze vraag niet."


def ask(
    query: str,
    index: SearchIndex,
    embedder: Embedder,
    generator: Generator,
    k: int = 5,
) -> Answer:
    hits = hybrid_search(index, embedder, query, size=k)
    sources = [Source(h.document_id, h.text or "") for h in hits]
    retrieved_ids = {s.document_id for s in sources}

    answer = generator.generate(query, sources)

    # Grounding guard: keep only citations that are in the retrieved set. Empty
    # surviving set -> ungrounded result, never the model's (possibly fabricated)
    # prose. De-dupe while preserving order.
    verified: list[str] = []
    for cid in answer.citations:
        if cid in retrieved_ids and cid not in verified:
            verified.append(cid)

    if not verified:
        return Answer(text=NO_GROUNDED_ANSWER, citations=[])
    return Answer(text=answer.text, citations=verified)
