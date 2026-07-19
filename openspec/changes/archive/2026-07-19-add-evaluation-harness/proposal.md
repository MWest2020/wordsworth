## Why

To know whether wordsworth's retrieval is any good — and to compare
configurations (BM25 vs hybrid) against the thesis numbers — we need a
reproducible evaluation harness computing the standard IR metrics: R-Precision,
Recall@10, MAP, and NDCG. The harness must be **collection-agnostic** and
**ranker-agnostic** so it works with the thesis's 47 queries + judgments OR a
self-built test collection, and against any of our rankers.

## What Changes

- Add **pure metric functions**: R-Precision, Recall@10, MAP (Average Precision),
  and NDCG@k, over a ranked list of document ids and (graded) relevance judgments.
- Add an **evaluation runner**: given a ranker callable (`query -> ranked doc
  ids`), a set of queries, and qrels, compute per-query metrics and their means.
- Add **loaders** for a standard on-disk format (TREC-style qrels + a queries
  TSV) so a real collection can be dropped in without code changes.
- The harness depends only on a ranker callable, so it evaluates BM25, hybrid, or
  any future ranker; it needs no database, OpenSearch, or Ollama itself.

## Capabilities

### New Capabilities
- `evaluation`: the IR metrics, the collection-/ranker-agnostic runner, and the
  test-collection loaders.

### Modified Capabilities
<!-- none: evaluation is a standalone capability consuming a ranker callable. -->

## Impact

- New module surface: `eval/metrics`, `eval/harness`, `eval/collection` (no new
  runtime dependency — pure Python + stdlib).
- No pipeline changes; the harness is invoked separately against a chosen ranker.
- **Open data decision (Mark's, separate from this change):** source the thesis's
  47 queries + relevance judgments, or build our own test collection. The harness
  is agnostic to that choice — it consumes whichever collection is provided.
- Does not touch `CLAUDE.md`, `.claude/agents/`, or CI.
