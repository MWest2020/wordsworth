## Why

Fixes issue #20 (part 1). The built query-result cache key omits `recall`:
`query_key(mode, size, query)` builds `f"q:{mode}:{size}:{query}"`
(`src/wordsworth/cache.py`), but `hybrid_search` has an output-affecting `recall`
arg (the RRF candidate-set size). Two calls with the same query+size but different
`recall` collide and serve a result computed under a different recall — breaking
the change's own rule that caching only affects latency, never output.

Latent today (the query cache is not yet wired into any caller), so this must be
corrected **before** the query cache is wired in.

## What Changes

- The query-result cache key SHALL include **every output-affecting parameter** —
  mode, query, `size`, AND `recall`.

## Capabilities

### Modified Capabilities
- `caching`: query-result cache key includes `recall`.

## Impact

- Corrects `query_key`/`cached_query` in `src/wordsworth/cache.py`. Embedding
  cache (per-element, explicit model id, no cached failures) is already correct.
  Does not touch `CLAUDE.md`, `.claude/agents/`, or CI.
- Archive-order: archive only after `add-caching` is archived — the baseline
  `openspec/specs/` does not carry this capability until then.
