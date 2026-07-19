# Design decisions — add-rate-limiting

## Token-bucket per client

A token-bucket per client key (API key if present, else source IP): `rate` tokens
refill per second up to `burst` capacity; each request costs one token. Empty
bucket → reject. Boring, standard, no dependency.

## Store abstraction

`RateLimitStore` holds per-key bucket state. Default in-memory (single instance);
a shared store (e.g. Redis) can back multiple instances later behind the same
interface. The middleware depends on the interface, not the backend.

## Response

On exceed: **HTTP 429** with a `Retry-After` header (seconds until a token frees).
Applies to the read endpoints (`/search`, `/hybrid`, `/ask`); `/health` and
`/metrics` are exempt so monitoring is never rate-limited.

## Config

Per-endpoint (or global) `rate` and `burst` from settings, so the CPU-heavy
`/ask` can be limited more tightly than `/search`.

## Not in scope

Quotas/billing, distributed coordination guarantees, adaptive limits.
