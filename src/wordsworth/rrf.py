"""Reciprocal Rank Fusion — pure, backend-agnostic, trivial to audit.

Given several ranked id-lists, fuse them: score(id) = sum_r 1/(k + rank_r(id)),
rank starting at 1. Higher is better. Ids missing from a list contribute nothing
for that list."""
from __future__ import annotations


def reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


def fuse_ranked_ids(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Fused ids, best first. Stable for equal scores by first-seen order."""
    scores = reciprocal_rank_fusion(rankings, k=k)
    return sorted(scores, key=lambda d: scores[d], reverse=True)
