# Design decisions — add-evaluation-harness

## Data model

- **qrels**: `dict[query_id, dict[doc_id, int]]` — graded relevance (0 = not
  relevant). Binary metrics treat any grade > 0 as relevant; NDCG uses the grade
  as gain. This one structure supports both binary and graded judgments.
- **queries**: `dict[query_id, str]`.
- **run**: for each query, a ranked `list[doc_id]` (best first), produced by the
  ranker under test.

## Metrics (exact definitions — implement these)

Let `rel` = {doc : qrels[q][doc] > 0}, `R = len(rel)`, `ranked` = ranked ids.

- **R-Precision**: `|rel ∩ ranked[:R]| / R` (0.0 if `R == 0`).
- **Recall@k** (k=10 default): `|rel ∩ ranked[:k]| / R` (0.0 if `R == 0`).
- **Average Precision**: mean of `precision@i` taken at each rank `i` where
  `ranked[i]` is relevant; `AP = (1/R) * Σ_i [ranked[i]∈rel] * (hits so far / i)`,
  1-indexed. 0.0 if `R == 0`. **MAP** = mean AP over queries.
- **NDCG@k**: `DCG@k / IDCG@k`, `DCG@k = Σ_{i=1..k} gain_i / log2(i+1)` with
  `gain_i = qrels[q].get(ranked[i], 0)`; `IDCG@k` = same over grades sorted
  descending. 0.0 if `IDCG@k == 0`.

All metrics are **pure functions** of (ranked ids, qrels-for-query) — unit-tested
against hand-computed examples, no I/O.

## Runner (collection- and ranker-agnostic)

`evaluate(search, queries, qrels, k=10) -> report` where `search: (query_text) ->
list[doc_id]`. For each query id present in qrels: run `search`, compute the four
metrics, collect. Report shape:

```
{"per_query": {qid: {"r_precision","recall@10","map"(=AP),"ndcg@10"}},
 "aggregate": {"r_precision","recall@10","map","ndcg@10"}}   # means over queries
```

The ranker is a plain callable, so BM25 (`index.search`), hybrid
(`hybrid.hybrid_search` adapted to return ids), or any future ranker plugs in.
The harness imports no database/OpenSearch/Ollama.

## On-disk collection format (so real data drops in)

- **qrels**: TREC format, whitespace-separated `query_id  0  doc_id  relevance`
  per line (the `0` is the ignored iteration column).
- **queries**: TSV, `query_id<TAB>query text` per line.

Loaders return the in-memory dicts above; the core never touches files. This lets
the thesis's 47 queries + judgments — or a self-built collection — be evaluated
without code changes.

## Scope note

**Not** in scope: sourcing the actual relevance judgments (Mark's decision —
thesis qrels vs self-built) and wiring a CLI/live run against OpenSearch+Ollama.
This change is the harness; feeding it a real collection is a follow-up.
