"""Collection- and ranker-agnostic evaluation runner.

`evaluate(search, queries, qrels, k)` runs the ranker callable once per query id
present in qrels, computes the four metrics, and returns per-query values plus
aggregate means over the queries. It depends on nothing but the callable — no
database, search engine, or embedding service. A qrels query id with no query
text is a hard error, not a silent skip (no silent fallbacks)."""
from __future__ import annotations

from collections.abc import Callable, Mapping

from .metrics import average_precision, ndcg_at_k, r_precision, recall_at_k

Ranker = Callable[[str], list[str]]
Qrels = Mapping[str, Mapping[str, int]]
Queries = Mapping[str, str]

_METRICS = ("r_precision", "recall@10", "map", "ndcg@10")


def evaluate(
    search: Ranker,
    queries: Queries,
    qrels: Qrels,
    k: int = 10,
) -> dict:
    """Return {"per_query": {qid: {metric: value}}, "aggregate": {metric: mean}}."""
    per_query: dict[str, dict[str, float]] = {}
    for qid, query_rels in qrels.items():
        if qid not in queries:
            raise KeyError(f"query id {qid!r} in qrels has no query text")
        ranked = list(search(queries[qid]))
        per_query[qid] = {
            "r_precision": r_precision(ranked, dict(query_rels)),
            "recall@10": recall_at_k(ranked, dict(query_rels), k),
            "map": average_precision(ranked, dict(query_rels)),
            "ndcg@10": ndcg_at_k(ranked, dict(query_rels), k),
        }
    return {"per_query": per_query, "aggregate": _aggregate(per_query)}


def _aggregate(per_query: dict[str, dict[str, float]]) -> dict[str, float]:
    n = len(per_query)
    if n == 0:
        return {metric: 0.0 for metric in _METRICS}
    return {
        metric: sum(row[metric] for row in per_query.values()) / n
        for metric in _METRICS
    }
