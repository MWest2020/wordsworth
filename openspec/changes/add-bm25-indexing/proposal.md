## Why

The PoC's goal is a searchable corpus. With de-identified text now flowing
through the pipeline, the last PoC step is to index it and expose keyword search.
This is fase 3: BM25 over the anonymized (or pseudonymized) corpus, on
OpenSearch — one system that also carries dense+hybrid/RRF in fase 4, Apache-2.0,
thesis-compatible. The chunking granularity is a first-order decision and is
settled here, before any index code.

## What Changes

- **Chunking decision: document-level for the PoC.** One index document per
  source document. It is the unit the thesis metrics (Recall@10, MAP) are
  measured on, so results stay directly comparable, and re-indexing ~1–2k docs is
  cheap if fase 4 (dense) later needs passage-level. Rationale in design.md.
- Introduce a **`SearchIndex` protocol** (driver/protocol pattern) with a `Hit`
  result type, plus an **`InMemoryIndex`** test double.
- Add an **`OpenSearchIndex`** driver: BM25 over a `text` field with the built-in
  **Dutch analyzer** (the corpus is Dutch), document id = source document id
  (idempotent upserts).
- Make the **`index` transition real**: push the anonymized text + metadata to
  the injected `SearchIndex`, then transition to `indexed`. **BREAKING** to stub.
- Expose **keyword search via the API** (`GET /search?q=`).

## Capabilities

### New Capabilities
- `search`: the `SearchIndex` seam, the OpenSearch BM25 driver (Dutch analyzer,
  document-level), and the search API.

### Modified Capabilities
- `document-lifecycle`: the `index` transition becomes real (idempotent upsert;
  index failure is transient/retryable, leaving the document in `anonymized`).

## Impact

- New dependency: `opensearch-py` (Apache-2.0).
- New module surface: `search_index`, `opensearch_index`; config for the
  OpenSearch URL + index name; a `/search` API endpoint.
- `pipeline.process()` gains an injected `search_index` (defaults to OpenSearch
  from config; tests inject the in-memory double).
- Indexing is a cross-system write: it is idempotent (id = document_id), so a
  crash between index and commit is safe — resume re-indexes and overwrites.
- No cloud, local OpenSearch. Does not touch `CLAUDE.md`, `.claude/agents/`, CI.
