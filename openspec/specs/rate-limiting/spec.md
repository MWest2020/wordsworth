# rate-limiting Specification

## Purpose

Keeping one caller from consuming the instance.

Deliberately small: per-client limits, a 429 when exceeded, and a swappable
store. The store is pluggable because a single process and a multi-replica
deployment need different answers, and hard-coding the first makes the second a
rewrite.

It is a protection, not a billing mechanism — the point is that the pipeline
stays responsive for everyone, including the batch that is halfway through.
## Requirements
### Requirement: Per-client rate limiting

The API SHALL rate-limit requests per client (API key or source IP) using a
token-bucket with configurable rate and burst, applied to the read endpoints
(`/search`, `/hybrid`, `/ask`). `/health` and `/metrics` SHALL be exempt.

#### Scenario: Requests within the limit succeed

- **WHEN** a client makes requests within its configured rate
- **THEN** the requests are served normally

#### Scenario: Monitoring endpoints are never limited

- **WHEN** `/health` or `/metrics` is called repeatedly
- **THEN** they are not rate-limited

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

