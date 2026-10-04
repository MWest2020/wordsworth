# SPDX-License-Identifier: MIT
"""Passages, for candidate 2 of change long-documents-rank-fairly.

One embedding per whole document stands for everything in it, so a long
document sits further from any one question than a short one vaguely about the
same thing. Scoring a document by its best passage removes that by
construction: a long document then has many chances, not one averaged one.

The split is a fixed rule, not tuned: windows of ``WORDS`` words that start
every ``STRIDE`` words, so neighbours overlap by ``WORDS - STRIDE``. 200 words
is about a paragraph -- short enough that one subject dominates, well inside
bge-m3's context. One setting, measured as one; other sizes are not measured.
"""
from __future__ import annotations

from zeef.similarity import cosine

# The rule lives in production now (wordsworth.passages); the evaluation uses the
# same one, so what was measured is what is built.
from ..passages import STRIDE, WORDS, split  # noqa: F401,E402


def best_passage_scores(query_vector: list[float],
                        passages: dict[str, list[list[float]]]) -> dict[str, float]:
    """Each document's score: the cosine of its best passage."""
    return {doc: max(cosine(query_vector, v) for v in vectors)
            for doc, vectors in passages.items() if vectors}
