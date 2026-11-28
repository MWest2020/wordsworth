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
rate limit, its 429 audit and `GET /v1/metrics` (`key-service-open-limits`),
the two deletions and the key-lifecycle chain (`key-service-delete`), and
the two reveal routes below (`key-service-reveal`, this one).

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

## `DELETE /v1/originals/{document_id}`

Crypto-shredding (ADR-0008): destroys every `document_keys` row sealed for
`document_id` and evicts them from this process's unwrap cache. Idempotent —
a second call destroys nothing. Which rows a deletion destroys when an
object key is shared between documents is an open question of
`key-service-delete`'s proposal, settled before `key-service-cutover` sends
any traffic; today every row the service sealed for the document goes.

| Case | Status | Body |
|---|---|---|
| no or unknown service token | 401 | `{"detail": "invalid or missing service token"}` |
| otherwise | 200 | `{"destroyed": n}` — `n` is 0 the second time |

After this call, `POST /v1/originals/{document_id}/open` for any of this
document's object keys answers 404 (`key-service-originals`).

One `access_audit` record per call (`event = "delete_originals"`, the
count) and one key-lifecycle event (`action = "keys_destroyed"`, the
document, the destroyed key ids) — both in the transaction that destroys
the keys.

## `DELETE /v1/documents/{document_id}`

Destroys the document's keys (as above), removes its token-registry rows,
every `pii_mappings` row no other document is still registered for, and
every grant scoped to the document (`grants.document_id` = the id) — an
unscoped grant survives. Leaves a tombstone that keeps only the document's
id and domain.

| Case | Status | Body |
|---|---|---|
| no or unknown service token | 401 | `{"detail": "invalid or missing service token"}` |
| document already tombstoned | 200 | `{"keys": 0, "tokens": 0, "mappings": 0, "grants": n}` — the tombstone is unchanged; `grants` counts any scoped grant created since (normally 0) |
| document never seen (no `known_documents` row) | 200 | `{"keys": 0, "tokens": 0, "mappings": 0, "grants": n}` — no tombstone is written (the service does not know a domain to write); a grant may still name the id and is deleted and counted; a later `pseudonymise` of the id registers it fresh |
| otherwise | 200 | `{"keys": n, "tokens": n, "mappings": n, "grants": n}` |

A value another document still holds survives, also when that other
document is being pseudonymised at the same moment (the registry lock
decides "no other document holds this token" the same way for both, so the
mapping is kept whichever commits first). After this call, `POST
/v1/pseudonymise` or `POST /v1/originals/{document_id}/seal` of the same id
answers 410.

One `access_audit` record per call (`event = "delete_document"`, the
counts) and one key-lifecycle event (`action = "document_deleted"`, the
document, the destroyed key ids, the deleted grant ids) — both in the
transaction that does the deletion. Never a 404: a deletion must not be
blockable, and wordsworth may delete a document that was never
pseudonymised.

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

## `POST /v1/reveal/decide`

Is this caller covered for this document, and for which types. Decides
only — decrypts nothing, writes no record (design.md "Requests", "Order
inside the service"). wordsworth calls this before reading anything of its
own about the document (`key-service-cutover`); this change ships the
route with no traffic.

Request (JSON):

```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "grant_id": "a1b2c3",
  "types": ["PERSON"],
  "assertion": "<the raw Keycloak JWT wordsworth received>",
  "vc": null
}
```

`types` null or absent means "everything the grant permits". The person is
identified by `assertion` — a signed assertion the service verifies itself
(see the how-to's "Identity" section) — never by the calling service's
token, which only names *which service* is calling.

| Case | Status | Body |
|---|---|---|
| no or unknown service token | 401 | `{"detail": "invalid or missing service token"}` |
| malformed body | 422 | validation detail |
| `KEYSERVICE_OIDC_ISSUER` or `KEYSERVICE_OIDC_AUDIENCE` unset | 503 | `{"detail": "reveal not configured"}` |
| assertion missing, forged, expired, not yet valid, wrong issuer, or foreign audience | 401 | `{"detail": "assertion not accepted"}`, the same body for every reason |
| unknown grant, revoked, expired, scoped to another document or recipient, another domain, unknown document, or a global grant not allowed | 403 | `{"detail": "grant not applicable"}` |
| covered, a presented VC is rejected | 403 | `{"detail": "vc rejected: <reason>"}` |
| covered, document tombstoned | 410 | `{"detail": "document deleted"}` |
| otherwise | 200 | `{"document_id": "...", "authorized_types": [...], "withheld_types": [...]}` |

Never 404 or 409. No statement reads `known_documents`, `document_tokens`,
`pii_mappings` or `key_vault` for a grant that fails before the document is
read (design.md "Order inside the service").

## `POST /v1/reveal`

Decides again, from scratch — no decision id, no state shared with a
prior `decide` call — and reveals the requested tokens that are
registered for the document and of an authorised type. Request: the
`decide` body plus `tokens` (the distinct tokens in the document's current
text) and `view` (`"text"` or `"pdf"`).

```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "grant_id": "a1b2c3",
  "types": null,
  "assertion": "<the raw Keycloak JWT>",
  "vc": null,
  "tokens": ["[PERSON:5c93c3df]"],
  "view": "text"
}
```

At most `KEYSERVICE_REVEAL_MAX_TOKENS` (default 10000) tokens; more is
answered 413, checked before anything else but the service token.

| Case | Status | Body |
|---|---|---|
| no or unknown service token | 401 | `{"detail": "invalid or missing service token"}` |
| malformed body | 422 | validation detail |
| more tokens than the limit | 413 | `{"detail": "too many tokens (limit N)"}`, nothing decrypted |
| not configured / assertion rejected / grant refusal / VC rejected / tombstoned | same as `decide`, above | same |
| covered, Transit unreachable or sealed | 503 | `{"detail": "key service unavailable"}`, no record |
| otherwise | 200 | see below |

A token not registered for this document, not of an authorised type, with
no mapping, or whose key does not resolve, is left out of the answer
silently — the response never says whether it exists elsewhere. 200 body:

```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "authorized_types": ["PERSON"],
  "withheld_types": [],
  "resolved_tokens": ["[PERSON:5c93c3df]"],
  "resolved_types": ["PERSON"],
  "values": {"[PERSON:5c93c3df]": "Jan Jansen"},
  "audit": {"seq": 1, "hash": "...", "actor": "ontvanger@example.com",
            "grant_id": "a1b2c3", "caller": "ontvanger@example.com"}
}
```

`values` is present only for `view = "text"`; the PDF view's body has no
`values` key at all — the PDF is drawn from the original page, never
assembled here. One `access_audit` record per successful call
(`event = "reveal"`): the document, the calling service, the verified
caller, the grant's recipient (`actor`), `grant_id` (and `role` /
`global_by_role` where the grant has a role), `view`, `requested_types`,
`requested_all`, `authorized_types`, the resolved `pseudonyms`, their
`types` and AVG `categories` — never a clear value. A refusal (any status
above but 200) writes no record and no log line names its cause, an id, or
the document's existence or state.

## Not in this change

- `service_state`'s own schema and drift test — see the how-to.
- The alert on open volume (a homelab manifest) and the scraper's own
  service token (a homelab PR) — see the how-to.
- Which key rows a deletion destroys when an object key is shared between
  documents, and wordsworth calling these routes — both
  `key-service-cutover`.
- Grant/role *management* endpoints (issue, revoke, create role, toggle a
  role) — `key-service-cutover`; grants and roles are seeded as rows until
  then.
- `POST /v1/export` — see `key-export-escrow`.
