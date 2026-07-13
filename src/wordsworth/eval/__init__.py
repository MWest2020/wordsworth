"""IR evaluation harness: pure metrics, a ranker-/collection-agnostic runner, and
loaders for a standard on-disk test collection.

Consumes a ranker callable (`query text -> ranked doc ids`) plus qrels/queries; it
imports no database, search engine, or embedding service, so it evaluates BM25,
hybrid, or any future ranker unchanged."""
from .collection import load_qrels, load_queries
from .harness import evaluate
from .metrics import average_precision, ndcg_at_k, r_precision, recall_at_k

__all__ = [
    "average_precision",
    "ndcg_at_k",
    "r_precision",
    "recall_at_k",
    "evaluate",
    "load_qrels",
    "load_queries",
]
