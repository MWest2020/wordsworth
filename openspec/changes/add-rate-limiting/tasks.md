# Tasks — add-rate-limiting

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. Limiter
- [ ] 1.1 `rate_limit.py`: token-bucket + `RateLimitStore` interface + in-memory store
- [ ] 1.2 Config: per-endpoint/global rate + burst
- [ ] 1.3 Tests: within-limit passes; over-limit rejected; bucket refills over time

## 2. Middleware
- [ ] 2.1 API middleware keyed by API key/IP on /search, /hybrid, /ask;
      exempt /health and /metrics; 429 + Retry-After on exceed
- [ ] 2.2 Tests: 429 with Retry-After when exceeded; monitoring endpoints exempt
