---
status: draft
last_reviewed: 2026-11-28
---

# Key service — API reference

This is the key service's own API (ADR-0009), a different process and
database from wordsworth's. See [the how-to](../how-to/key-service.md) for
deployment, its database and failure modes.

The surface grows one change at a time: the process boundary and its
authentication (`key-service-skeleton`), `POST /v1/pseudonymise`
(`key-service-pseudonymise`), seal and open (`key-service-originals`), the
rate limit, its 429 audit and `GET /v1/metrics` (`key-service-open-limits`,
this one), then `key-service-delete` and `key-service-reveal`.

## `GET /health`

Liveness probe. No `Authorization` header needed.

- **200** `{"status": "ok"}` — the process is up and its own database is
  reachable.
- **503** `{"detail": "database unreachable"}` — the process is up but its
  database is not.

## `/v1/*`

No route under `/v1/` does anything yet. Every request under this prefix is
authenticated the same way, before routing:

### Authentication

`Authorization: Bearer <service token>`, checked against
`KEYSERVICE_SERVICE_TOKENS` in constant time.

- **401** `{"detail": "invalid or missing service token"}` — missing header,
  malformed header, unknown token, or an empty configured token set (every
  `/v1` call then refuses, by design — see the how-to). Returned before the
  request body is read and before any database access, by a pure ASGI
  middleware, not a route dependency.

A valid token authenticates the *calling service*, recorded as
`service_caller` for later audit records — it is never a person's identity.
`key-service-reveal` adds how a person's identity travels and is verified
separately.

## `POST /v1/pseudonymise`

Per document, a batch of (type, value) pairs in; tokens out. The service
derives each value's keyed `[TYPE:hash8]` token (wordsworth's own
derivation, unchanged), stores the encrypted value, registers each
returned token for the document (`source = minted`) and records the
document's domain on first sight. No value, hash of a value, or key id is
ever in the response.

Request (JSON):

```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "domain": "example",
  "items": [{"type": "PERSON", "value": "Jan Jansen"}]
}
```

`items` may be empty — that registers the document and its domain without
minting any token. At most `KEYSERVICE_PSEUDONYMISE_MAX_ITEMS` (default
1000) items per call; a larger document sends several calls.

A `type` is valid when it matches `[A-Za-z0-9_]+` (case-insensitive — the
service upper-cases it). There is no closed list of known types: an
unrecognised detector label is accepted, not refused. `domain` must be
non-empty and contain no `/`.

| Case | Status | Body |
|---|---|---|
| no or unknown service token | 401 | `{"detail": "invalid or missing service token"}` |
| malformed body, invalid type label or domain, too many items | 422 | validation detail, never echoing a value |
| document already known in another domain | 409 | `{"detail": "document is registered in another domain"}` |
| document tombstoned (deleted) | 410 | `{"detail": "document deleted"}` |
| a mapping key is needed and Transit is unreachable or sealed | 503 | `{"detail": "key service unavailable"}`, nothing committed |
| otherwise | 200 | `{"document_id": "...", "tokens": ["[PERSON:5c93c3df]", ...]}`, one token per item, same order as `items` |

One `access_audit` record per call (`event = "pseudonymise"`): the document,
the calling service, the number of items per type, and the number of new
registry rows. No value or token is ever written to that record, or to any
log line.

## `POST /v1/originals/{document_id}/seal`

The original's bytes as `application/octet-stream`; query `domain` and
`object_key`. Mints a data key wrapped under the KEK for `domain` on first
seal of an object key, or reuses the existing one on a later seal of the
same object key for the same document — never a second data key for one
object key. Up to `KEYSERVICE_MAX_ORIGINAL_BYTES` (default 100 MiB); the
413 is enforced after FastAPI has buffered the whole body into memory.

| Case | Status | Body |
|---|---|---|
| no or unknown service token | 401 | `{"detail": "invalid or missing service token"}` |
| body over `KEYSERVICE_MAX_ORIGINAL_BYTES` | 413 | `{"detail": "original exceeds the configured size bound"}` |
| `domain` or `object_key` missing, `domain` empty or containing `/` | 422 | validation detail |
| document registered in another domain | 409 | `{"detail": "document is registered in another domain"}` |
| object key's row belongs to another document | 409 | `{"detail": "object key belongs to another document"}` |
| document tombstoned | 410 | `{"detail": "document deleted"}` |
| Transit unreachable or sealed | 503 | `{"detail": "key service unavailable"}`, nothing committed |
| otherwise | 200 | sealed bytes, `X-Key-Id` header |

One `access_audit` record per call (`event = "seal"`): the document,
`object_key`, the key id, and whether the key was minted or reused.

## `POST /v1/originals/{document_id}/open`

The sealed bytes as `application/octet-stream`; query `object_key` and
`purpose`, one of `process`, `reanonymize`, `ocr_recovery`, `redacted_pdf`,
`reveal_pdf`, `seal_verify`. Fails closed: a tampered wrapped key or a
tampered sealed object never returns plaintext.

Rate-limited per calling service: a token bucket,
`KEYSERVICE_OPEN_RATE_PER_MINUTE` (default 120) refill,
`KEYSERVICE_OPEN_BURST` (default 30) capacity, checked after `purpose` and
`object_key` are validated — so the order is 401, then 422, then 429.

| Case | Status | Body | Audit |
|---|---|---|---|
| no or unknown service token | 401 | `{"detail": "invalid or missing service token"}` | none |
| `purpose` missing or not in the list; malformed query | 422 | validation detail | none |
| body over `KEYSERVICE_MAX_ORIGINAL_BYTES` | 413 | `{"detail": "sealed object exceeds the configured size bound"}` | none |
| over the calling service's rate limit | 429, `Retry-After` header | `{"detail": "rate limit exceeded"}` | counted always; the window's *first* refusal writes `open_refused` (`reason = "rate"`); that refusal also writes `open_refused_summary` (window start, count) for the *previous* window, if one existed — never one record per refusal |
| no key row for `object_key` under this `document_id` | 404 | `{"detail": "no key for this object"}` | `open_refused`, `reason = "no_key"` |
| the key backend gave no answer (connect/timeout, HTTP 5xx) | 503 | `{"detail": "key service unavailable"}` | none |
| the wrapped key or the sealed object does not authenticate | 409 | `{"detail": "sealed object does not open"}` | `open_failed`, `reason = "unwrap"` or `"envelope"` |
| otherwise | 200 | the plaintext | `open`, document, `object_key`, purpose |

## `GET /v1/metrics`

Prometheus text format, behind the same service token as every other `/v1`
route — no change to `ServiceTokenMiddleware`, since it already covers every
path under `/v1/`. Never rate-limited: the app mounts no path-keyed limiter
middleware, so there is no rule for this route to be exempt from.

- `keyservice_opens_total{caller,purpose}` — counted from `access_audit`
  `open` records at scrape time.
- `keyservice_open_refusals_total{caller,reason}` — the service's own
  refusal counters (`service_state`).

No value, document id or object key appears in the output.

| Case | Status | Body |
|---|---|---|
| no or unknown service token | 401 | `{"detail": "invalid or missing service token"}` |
| otherwise | 200 | Prometheus text |

## Not in this change

- `service_state`'s own schema and drift test — see the how-to.
- The alert on open volume (a homelab manifest) and the scraper's own
  service token (a homelab PR) — see the how-to.
- The two deletions and the key-lifecycle chain — see `key-service-delete`.
- Reveal and identity verification — see `key-service-reveal`.
- `POST /v1/export` — see `key-export-escrow`.
