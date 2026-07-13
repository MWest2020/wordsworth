# Tasks — add-rate-limiting

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.
SOFT DEPENDENCY: `/ask` arrives with add-rag, `/metrics` with add-observability;
build config-driven so this change works before and after those land.

## 1. Limiter
- [ ] 1.1 `rate_limit.py`: token-bucket + `RateLimitStore` interface + in-memory store
- [ ] 1.2 Config: per-endpoint/global rate + burst
- [ ] 1.3 Tests: within-limit passes; over-limit rejected; bucket refills over time

## 2. Middleware
- [ ] 2.1 API middleware, config-driven limited/exempt sets (not a hardcoded route
      list); keyed by API key when present else source IP (IP-only until auth
      exists); matches by path and is inert for unregistered routes; 429 +
      Retry-After (non-negative integer) on exceed
- [ ] 2.2 Tests: 429 with Retry-After when exceeded; exempt endpoints not limited;
      middleware inert when a limited route is not registered
