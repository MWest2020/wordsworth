## Why

The evaluation harness computes metrics given a ranker callable and a collection;
this change wires it to the real system and runs it against the **thesis
collection** (Pilkes' 47 queries + relevance judgments) so our BM25 and hybrid
configurations produce R-Precision, Recall@10, MAP, and NDCG numbers directly
comparable to the thesis. Using the existing judgments (not a self-built set)
keeps the comparison honest and legible to third parties.

## What Changes

- Add **ranker adapters** exposing our search as the harness's `search(query) ->
  ranked doc ids` callable: one for **BM25** (`index.search`) and one for
  **hybrid** (`hybrid_search`), each returning the documents' external ids and
  retrieving to a configurable **depth** (≥ `max(k, max R)`, not the metric
  cutoff `k`; hybrid raises `recall` to match) so MAP/R-Precision are not
  deflated.
- Add an **evaluation run**: load the thesis collection (TREC qrels + TSV queries
  via the harness loaders), run each configuration over the indexed corpus,
  compute the four metrics, and emit a **report** (per-config aggregates), runnable
  from a CLI.
- Match qrels ids to indexed documents via the document's **external id**
  (`object_key`), so hits map back to the ids the judgments use.

## Capabilities

### New Capabilities
- `evaluation-run`: ranker adapters + a runnable evaluation over a real collection
  and corpus, producing a comparable metrics report.

## Impact

- **Depends on `add-evaluation-harness`** (metrics, runner, loaders) — build that
  first. Reuses hybrid search + embeddings; no new dependency.
- **Operator inputs (Mark's):** the thesis qrels/queries files and the thesis
  corpus ingested into wordsworth keyed by the qrels' document ids. A real hybrid
  run needs OpenSearch + local bge-m3 embeddings.
- Read-only evaluation; no pipeline change. Does not touch `CLAUDE.md`,
  `.claude/agents/`, or CI.
