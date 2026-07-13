# Design decisions — add-rate-limiting

## Token-bucket per client

A token-bucket per client key (API key if present, else source IP): `rate` tokens
refill per second up to `burst` capacity; each request costs one token. Empty
bucket → reject. Boring, standard, no dependency.

The API has no authentication today (`create_app` extracts no API key), so the
key is **source-IP** in practice; the API-key branch is dormant until an auth
mechanism lands. `Retry-After` is a non-negative integer (ceil of seconds until
the next token frees, ≈ `1/rate`).

## Store abstraction

`RateLimitStore` holds per-key bucket state. Default in-memory (single instance);
a shared store (e.g. Redis) can back multiple instances later behind the same
interface. The middleware depends on the interface, not the backend.

## Response

On exceed: **HTTP 429** with a `Retry-After` header (seconds until a token frees).

## Config-driven endpoint sets (no hardcoded routes)

The limited and exempt sets come from config, not a fixed route list. `/ask`
(from `add-rag`) and `/metrics` (from `add-observability`) do not exist yet, so
hardcoding them would couple this change to unbuilt routes. Instead: limit the
read endpoints present, exempt a configurable set including `/health` and
`/metrics`. The middleware matches by path and is a no-op for routes an app
instance did not register (routes are conditional on injected dependencies). This
keeps the change independently buildable now and correct once `/ask`/`/metrics`
land — a soft dependency, not a build-order blocker.

## Config

Per-endpoint (or global) `rate` and `burst` from settings, so the CPU-heavy
`/ask` can be limited more tightly than `/search`.

## Not in scope

Quotas/billing, distributed coordination guarantees, adaptive limits.
