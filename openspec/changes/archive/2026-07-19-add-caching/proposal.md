## Why

Fase 6 (productieklaar). CPU embeddings and repeated queries are the expensive
paths; caching cuts latency and load. A cache is strictly an optimization — a
miss recomputes, so it can never change results.

## What Changes

- Introduce a **`Cache` protocol** (get/set) with an in-memory LRU default and a
  pluggable backend.
- **Cache embeddings** keyed by a content hash of the input text.
- **Cache search/hybrid results** keyed by the query (and size).
- Provide explicit **bypass/invalidate** so a re-index or model change cannot
  serve stale results.

## Capabilities

### New Capabilities
- `caching`: the cache seam, embedding and query-result caching, and invalidation.

## Impact

- New module surface: `cache`. In-memory default (no new dependency); a shared
  backend (e.g. Redis) can be added later behind the same protocol.
- Caching is optional and correctness-neutral. Does not touch `CLAUDE.md`,
  `.claude/agents/`, CI.
