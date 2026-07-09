# Tasks — add-thesis-evaluation

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.
DEPENDS ON: add-evaluation-harness (metrics, runner, loaders) — build that first.

## 1. Ranker adapters
- [ ] 1.1 `eval/adapters.py`: `bm25_adapter(index, k)` and
      `hybrid_adapter(index, embedder, k)` returning `search(query) -> [object_key]`
- [ ] 1.2 Tests (in-memory index + deterministic embedder): each adapter returns
      ranked external ids for a query

## 2. Evaluation run
- [ ] 2.1 `eval/run.py`: `run_evaluation(configs, queries, qrels, k) -> report`
      (per-config aggregates via the harness `evaluate`)
- [ ] 2.2 Tests: report has the four metrics per configuration on a small synthetic
      collection whose qrels ids are the documents' object_keys

## 3. CLI
- [ ] 3.1 `python -m wordsworth.eval.run --qrels ... --queries ... --config bm25,hybrid`
      loads the collection, runs, prints the report
- [ ] 3.2 Test: CLI on fixture files prints a report with per-config metrics

## 4. Docs
- [ ] 4.1 Document the precondition: ingest the eval corpus with `object_key` =
      the qrels' document ids; note OpenSearch + local bge-m3 needed for a hybrid run
