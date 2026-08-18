## Why

Idempotent ingest skipped a document if the DB said it had ever been `indexed`.
But the DB (audit chain) can outlive an OpenSearch index recreation: after the
index was rebuilt without clearing the DB, the skip stranded documents — the DB
said "indexed" so they were skipped, yet they were absent from the actual index
(observed as a 739-in-DB vs 283-in-index mismatch). "Already done" must be judged
against the source of truth for *searchable*, which is the index.

## What Changes

- `SearchIndex` gains `has_object_key(object_key) -> bool`; implemented on
  `OpenSearchIndex` (a `count` term-query on `object_key`) and `InMemoryIndex`.
- `POST /ingest` skip-existing now checks the **search index** for the content
  key, not the DB. So a document is skipped only if it is actually in the index;
  recreating the index correctly makes those documents eligible again, and a
  re-run rebuilds exactly what is missing.

## Capabilities

### Modified Capabilities
- `deployment`: idempotent ingest recognises already-indexed documents against
  the index (source of truth), not DB history.

## Impact

- Code: `search_index.py` (protocol + InMemoryIndex), `opensearch_index.py`
  (`has_object_key`), `api.py` (skip uses the index). No pipeline/schema change.
  Tests added.
