## ADDED Requirements

### Requirement: Per-client rate limiting

The API SHALL rate-limit requests per client using a token-bucket with
configurable rate and burst. The limited and exempt endpoint sets SHALL be
**config-driven**, not a hardcoded route list: the limiter applies to the read
endpoints that exist (`/search`, `/hybrid`, and `/ask` once `add-rag` adds it)
and exempts a configurable set including `/health` and `/metrics` (the latter
arrives with `add-observability`). The middleware SHALL match by path and be
inert for routes not registered in a given app instance (routes are registered
conditionally, e.g. an app built without a search index has no `/search`).

The client key SHALL be the API key when present, else the source IP. Until an
authentication/API-key mechanism exists, no API key is available, so keying is
**source-IP only**; the API-key branch is ready but dormant.

#### Scenario: Requests within the limit succeed

- **WHEN** a client makes requests within its configured rate
- **THEN** the requests are served normally

#### Scenario: Monitoring endpoints are never limited

- **WHEN** an endpoint in the configured exempt set (e.g. `/health`, `/metrics`)
  is called repeatedly
- **THEN** it is not rate-limited

### Requirement: 429 when exceeded

Exceeding the limit SHALL return HTTP 429 with a `Retry-After` header.

#### Scenario: Over-limit client is throttled

- **WHEN** a client exceeds its rate
- **THEN** it receives HTTP 429 with a `Retry-After` header

### Requirement: Swappable limiter store

The limiter SHALL keep per-key state behind a store interface with an in-memory
default, so a shared backend can support multiple instances later.

#### Scenario: In-memory store enforces the limit

- **WHEN** the in-memory store is used
- **THEN** per-client limits are enforced within a single instance
