# Design decisions — add-thesis-evaluation

## Ranker adapters (search as a callable)

The harness runner takes `search(query) -> ranked doc ids`. Provide thin adapters
parameterised by a retrieval **`depth`**, NOT the metric cutoff `k`:

- **BM25**: `lambda q: [h.object_key for h in index.search(q, size=depth)]`
- **hybrid**: `lambda q: [h.object_key for h in hybrid_search(index, embedder, q, size=depth, recall=depth)]`

`depth` MUST be at least `max(k, max R over queries)` (ideally the full corpus),
because R-Precision needs the top-R (R can exceed `k=10`) and AP needs the ranks
of all relevant docs — passing `size=k` would truncate the ranking to the metric
cutoff and deflate MAP/R-Precision (the same rule the harness states). For the
**hybrid** adapter `recall` must be raised to `depth` too: `hybrid_search` caps
its result at `recall` (default 50), so `size` alone cannot deepen it.

Both return the documents' **external id** (`object_key`), not the internal uuid,
so results line up with the thesis qrels (see id matching below). `object_key` is
`str | None`; the adapter SHALL skip/raise on a null key rather than emit `None`
into the ranking (the eval-corpus precondition guarantees non-null keys). Any
future ranker is just another adapter — the harness is unchanged.

## Id matching: qrels ids ↔ indexed documents

The thesis judgments reference documents by their native identifier. wordsworth
assigns its own uuid, but each document also carries an `object_key`. The corpus
for evaluation MUST be ingested with `object_key` = the qrels' document id, and
the adapters return `object_key`. Then `qrels[qid]` keys and the ranked ids share
one namespace. This is stated as a precondition, not solved in code — it is how
the operator loads the corpus.

## Run and report

`run_evaluation(configs, queries, qrels, k=10, depth=...) -> report`:
1. For each config (BM25, hybrid), build its adapter at retrieval `depth`
   (default `≥ max(k, max R over the qrels)`).
2. Call the harness `evaluate(adapter, queries, qrels, k)`.
3. Collect per-config aggregates into one report:
   `{config: {"r_precision","recall@10","map","ndcg@10"}}`.

Exposed via a CLI (`python -m wordsworth.eval.run --qrels ... --queries ...
--config bm25,hybrid`). Comparison to the thesis's own published numbers is done
by placing this report beside them — we compute *our* numbers on *their* collection.

## Boundaries

- **Depends on the harness** (`add-evaluation-harness`); this change adds only the
  adapters + run + report, no metric maths.
- A real hybrid run needs OpenSearch + local bge-m3 (Ollama). BM25-only can run
  without embeddings. Both are runtime, not part of the spec.
- Deterministic and read-only — no writes to the corpus, index, or audit trail.

## Not in scope

Reproducing the thesis's non-wordsworth systems (Azure, Notubiz, Woogle),
significance testing, and per-query error analysis UI.
