# Tasks — add-rate-limiting

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. Limiter
- [x] 1.1 `rate_limit.py`: token-bucket + `RateLimitStore` interface + in-memory store
- [x] 1.2 Config: per-endpoint/global rate + burst
- [x] 1.3 Tests: within-limit passes; over-limit rejected; bucket refills over time

## 2. Middleware
- [x] 2.1 API middleware keyed by API key/IP on /search, /hybrid, /ask;
      exempt /health and /metrics; 429 + Retry-After on exceed
- [x] 2.2 Tests: 429 with Retry-After when exceeded; monitoring endpoints exempt
