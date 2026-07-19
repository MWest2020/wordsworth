# Tasks — add-evaluation-harness

Done = green: every task ships with its tests in the same builder run.
NOTE: unchecked — for a Habitat builder to implement.

## 1. Metrics
- [x] 1.1 `metrics.py`: pure `r_precision`, `recall_at_k`, `average_precision`,
      `ndcg_at_k` per the exact definitions in design.md (graded qrels; >0 = relevant)
- [x] 1.2 Tests: hand-computed examples for each metric; earlier hits raise AP;
      ideal order -> NDCG 1.0; no-relevant -> 0.0 for all

## 2. Runner
- [x] 2.1 `harness.py`: `evaluate(search, queries, qrels, k=10) -> report`
      (per-query metrics + aggregate means); depends only on the callable
- [x] 2.2 Tests: a trivial/stub ranker over a synthetic collection yields the
      expected per-query and aggregate numbers; a second ranker scores worse

## 3. Collection loaders
- [x] 3.1 `collection.py`: `load_qrels` (TREC format) + `load_queries` (TSV) ->
      in-memory dicts
- [x] 3.2 Tests: round-trip parse of small fixture files; graded relevance preserved

## 4. End-to-end (synthetic)
- [x] 4.1 Evaluate an in-memory ranker (e.g. InMemoryIndex.search or hybrid with
      the deterministic embedder) over a small synthetic Dutch collection; assert
      sane, reproducible metrics. No external services required.
