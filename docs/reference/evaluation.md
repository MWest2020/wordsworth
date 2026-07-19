---
status: draft
last_reviewed: 2026-07-18
---

# Evaluation run

wordsworth's IR evaluation (`wordsworth.eval`) computes R-Precision, Recall@10,
MAP, and NDCG@10 for the BM25 and hybrid configurations over a standard test
collection (TREC qrels + TSV queries), e.g. the thesis's 47 queries and
relevance judgments.

## Running

```
python -m wordsworth.eval.run --qrels qrels.txt --queries queries.tsv \
    --config bm25,hybrid [--k 10]
```

The report prints the four aggregate metrics per configuration.

## Precondition: id matching

The qrels reference documents by their native identifier; wordsworth assigns
its own uuid. **The evaluation corpus MUST be ingested with `object_key` equal
to the qrels' document ids.** The ranker adapters return `object_key`, so the
ranked ids and the qrels ids share one namespace. This is an operator
responsibility when loading the corpus — it is not solved in code, and a hit
without an `object_key` is a hard error (no silent fallbacks).

## Runtime requirements

- **BM25** (`--config bm25`): a running OpenSearch with the corpus indexed.
- **Hybrid** (`--config bm25,hybrid`): additionally local bge-m3 embeddings via
  Ollama. Everything runs locally — no cloud APIs in the critical path.

The run is deterministic and read-only: it writes nothing to the corpus, the
index, or the audit trail.
