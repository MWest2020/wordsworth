## Why

Fase 6 (productieklaar). The public API (search, hybrid, ask) needs protection
from overload and abuse — especially the ask/embedding paths, which are CPU-heavy.

## What Changes

- Add **per-client rate limiting** on the API via a token-bucket, keyed by client
  (API key or IP), with configurable rate and burst.
- Return **HTTP 429** with a `Retry-After` hint when a client exceeds its limit.
- Keep the limiter behind a small store abstraction (in-memory default; a shared
  store can back multi-instance deployments later).

## Capabilities

### New Capabilities
- `rate-limiting`: per-client API rate limiting with 429 responses.

## Impact

- New API middleware; in-memory token-bucket by default (no new dependency).
  Applies to search/hybrid/ask endpoints. Local; no external service. Does not
  touch `CLAUDE.md`, `.claude/agents/`, CI.
