# Tasks — add-thesis-evaluation

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.
DEPENDS ON: add-evaluation-harness (metrics, runner, loaders) — build that first.

## 1. Ranker adapters
- [ ] 1.1 `eval/adapters.py`: `bm25_adapter(index, depth)` and
      `hybrid_adapter(index, embedder, depth)` returning
      `search(query) -> [object_key]`; retrieve to `depth` (≥ max(k, max R)), NOT
      the metric `k`; hybrid sets `size=depth` AND `recall=depth`; skip null keys
- [ ] 1.2 Tests (in-memory index + deterministic embedder): each adapter returns
      ranked external ids for a query; a depth > k returns more than k ids

## 2. Evaluation run
- [ ] 2.1 `eval/run.py`: `run_evaluation(configs, queries, qrels, k, depth) ->
      report` (per-config aggregates via the harness `evaluate`); depth defaults
      to ≥ max(k, max R over the qrels)
- [ ] 2.2 Tests: report has the four metrics per configuration on a small synthetic
      collection whose qrels ids are the documents' object_keys

## 3. CLI
- [ ] 3.1 `python -m wordsworth.eval.run --qrels ... --queries ... --config bm25,hybrid
      [--depth N]` loads the collection, runs, prints the report
- [ ] 3.2 Test: CLI on fixture files prints a report with per-config metrics

## 4. Docs
- [ ] 4.1 Document the precondition: ingest the eval corpus with `object_key` =
      the qrels' document ids; note OpenSearch + local bge-m3 needed for a hybrid run
