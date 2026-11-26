# Design

All routes below sit behind the skeleton's service token (401 first, before
the body is parsed). The caller is a service (`service_caller`, the token's
label); no person is involved and no user assertion is read. Request logging
drops the body and the response of every route here: no value, original byte
or key byte reaches a log.

Modules (each ≤ 200 lines): `api_pseudonymise.py`, `api_originals.py`,
`api_documents.py`, `stores.py` (the service's mapping store, key vault and
document keys over `KeyServiceBase`, implementing the same protocols as
wordsworth's: `MappingStore`, `KeyProvider`, `DocumentKeys`' interface),
`audit.py`, `rate_limit.py`. The token derivation, normalisation and
encryption are wordsworth's own functions (`Pseudonymizer.pseudonym`,
`normalization`, `crypto`, `originals_envelope`), called with the service's
stores; nothing about how a token is made changes. The import rules of
`key-service-skeleton` ("Reuse and imports") apply: `document_keys.kek_name_for`
gets the domain → KEK mapping as an argument and `DocumentKeys` gets its cache
size and TTL from the service's settings (`KEYSERVICE_ORIGINALS_KEK`,
`KEYSERVICE_ORIGINALS_KEK_BY_DOMAIN`, `KEYSERVICE_DOCUMENT_KEY_CACHE_SIZE`,
`KEYSERVICE_KEY_CACHE_TTL`), wordsworth's call sites keeping their defaults;
the tests of this change run under the fixture that makes `config.settings`
raise.

## Only reveal returns a clear value

No route of the service returns a clear mapping value to a calling service
without a verified person. The routes here return tokens, sealed bytes, opened
originals (for processing, audited and rate-limited) and counts; the only
route that returns mapping values is `/v1/reveal` (`key-service-reveal`), and
it needs a person's assertion and a grant. A later need for clear values
without a person (the box map, `key-service-cutover`) is met from the values
in memory during processing, not by a new route.

## The token registry

The registry is the service's. A row (`document_id`, `token`) exists only
because the service itself returned that token from `pseudonymise` for that
document (`source = minted`), or because the cutover copied it
(`source = copied_minted` or `copied_backfilled`, keeping wordsworth's
provenance). Nothing else writes it. A reveal (`key-service-reveal`)
reveals only tokens registered for the document it is asked about.

This is what makes the registry trustworthy against a compromised wordsworth:
to bind a token to a document it must send the value, and a value it already
knows is no secret. A value it does not know cannot be registered anywhere.

Registering never removes a token: re-pseudonymising a document adds the new
tokens and keeps the old ones, as `pseudonym_registry.register` does today (a
reveal in flight must not see the registry shrink). Only
`DELETE /v1/documents/{id}` removes rows.

wordsworth's own `document_pseudonyms` is not touched by this change.

## `known_documents`

The service knows a document from its first `pseudonymise` or `seal`, both of
which carry `domain`. The first call records (`id`, `domain`); a later call
for the same id with a different domain is refused (409), and a call for a
tombstoned id is refused (410). The domain recorded here is the one reveal
judges a grant against; wordsworth cannot change it afterwards.

## Locks

One order inside the service's database, for every writer below:

1. the registry advisory lock (`pg_advisory_xact_lock(4781)`, the service's
   own key) — taken by `pseudonymise`, `seal` and `DELETE /v1/documents`;
2. the `known_documents` row;
3. `document_keys` rows, by `object_key`, `FOR UPDATE`;
4. `pii_mappings` rows, by token: inserted `ON CONFLICT DO NOTHING` by
   `pseudonymise`, `FOR UPDATE` by a deletion;
5. the `key_lifecycle_events` chain lock (its own advisory key, chosen in the
   build next to 4781 and 4782 and written on `docs/reference/lock-order.md`),
   taken by a writer that records a key-lifecycle event;
6. the `access_audit` chain lock (its own advisory key, 4782), last: the audit
   stays the terminal leaf, nothing is taken after it.

`DELETE /v1/originals/{id}` and `DELETE /v1/documents/{id}` write both a
key-lifecycle event (destroyed keys, deleted grants) and an `access_audit`
record, so they take 5 then 6, in that order, in one transaction. Decided: put
key lifecycle before the audit. Rejected: audit before key lifecycle, which
would make the audit a non-terminal lock and every future lifecycle writer
reason about it; and two transactions (a lifecycle event, then the audit),
which leaves a destroyed key with no audit record if the second fails.
`docs/reference/lock-order.md` is settled first (see `tasks.md`): wordsworth's
page describes the key-lifecycle chain (4772) as "never together with 4771",
and that sentence is about wordsworth's database, not this one.

This is the service-side twin of #465: a deletion decides "no other document
holds this token" under lock 1, and a pseudonymise of the same value for
another document stores the mapping under lock 1 too, so either the deletion
sees the new registry row or the mapping is stored again after it.

## `POST /v1/pseudonymise`

Request (JSON): `{"document_id": UUID, "domain": str, "items": [{"type": LABEL,
"value": str}, ...]}`. `items` may be empty (that registers the document and
its domain). At most `KEYSERVICE_PSEUDONYMISE_MAX_ITEMS` (default 1 000, and
the setting is refused at startup above 5 000). The cap is there because lock 1
(4781) is held for the whole batch: 10 000 items held it long enough to stall
every other writer. Rejected: keeping 10 000 and shortening the lock by
committing in chunks, which would break "nothing committed" on a 503 and the
one-audit-record-per-call rule. A larger document sends several calls. The
measurement of how long lock 1 is held at the cap is taken at cutover (see
`tasks.md`), and the default is revisited from it.

| Case | Status | Body |
|---|---|---|
| no or unknown service token | 401 | `{"detail": "invalid or missing service token"}` |
| malformed body, unknown type label, too many items | 422 | validation detail, never echoing a value |
| document known in another domain | 409 | `{"detail": "document is registered in another domain"}` |
| document tombstoned | 410 | `{"detail": "document deleted"}` |
| a key is needed and Transit is unreachable or sealed | 503 | `{"detail": "key service unavailable"}`, nothing committed |
| otherwise | 200 | `{"document_id": UUID, "tokens": [str, ...]}`, one token per item, same order |

The response contains no value, no hash of a value and no key id. One
`access_audit` record per call: `event = "pseudonymise"`, the document, the
service caller, the number of items per type and the number of new registry
rows; no value, no token.

## `POST /v1/originals/{document_id}/seal`

Request: the original's bytes as `application/octet-stream`; query
`domain` and `object_key`. At most `KEYSERVICE_MAX_ORIGINAL_BYTES` (413
beyond). The service checks `known_documents` exactly as `pseudonymise` does
(409 other domain, 410 tombstoned, else record it), then mints and wraps a
data key and seals the bytes with the semantics of
`OriginalsStore.put_original` today, minus the object-store write: the
response is the sealed bytes (`application/octet-stream`, header `X-Key-Id`),
and wordsworth stores them. 503 when Transit is unreachable. Audit:
`event = "seal"`, document, `object_key`, key id.

## `POST /v1/originals/{document_id}/open`

Request: the sealed bytes as `application/octet-stream`; query `object_key`
and `purpose`. The purpose is one of `process`, `reanonymize`,
`ocr_recovery`, `redacted_pdf`, `reveal_pdf`, `seal_verify` (the readers of
`docs/reference/originals-readers.md` plus verification).

Order and answers:

| Case | Status | Audit |
|---|---|---|
| no or unknown service token | 401 | none |
| purpose missing or not in the list; malformed query | 422 | none |
| over the caller's rate | 429, `Retry-After` | one `open_refused` record per caller per 60-second window, with `reason = "rate"` and the number of refusals so far in that window (see below) |
| no key row for `object_key` under this document | 404 `{"detail": "no key for this object"}` | `open_refused`, `reason = "no_key"` |
| Transit unreachable or sealed | 503 `{"detail": "key service unavailable"}` | none (nothing was decided) |
| the wrapped key does not unwrap, or the envelope does not authenticate (tampered) | 409 `{"detail": "sealed object does not open"}` | `open_failed`, `reason = "unwrap"` or `"envelope"` |
| otherwise | 200, the plaintext | `open`, document, `object_key`, purpose |

The rate limit is a token bucket per service caller
(`KEYSERVICE_OPEN_RATE_PER_MINUTE`, default 120; `KEYSERVICE_OPEN_BURST`,
default 30), in the service's own `rate_limit_buckets`, keyed on the caller
label, not the path. A 404 here is no oracle: only a calling service with a
token reaches this route, and it is the one that stored the object.

A 429 costs no hash-chained write per refusal: a caller hammering the route
would otherwise turn every refusal into a write under the chain lock (4782),
slowing the audit for everyone. Every refusal is counted in
`keyservice_open_refusals_total`; the audit gets the first refusal of a caller
in a window as an `open_refused` record, and the window's final count is
written into one `open_refused_summary` record when the window closes or the
caller's next window opens. Rejected: one record per refusal (the write
amplification above); no audit at all (a refused burst is the signal an
investigation looks for). The other refusals (`no_key`, `unwrap`, `envelope`)
stay one record each: they are not caller-driven floods and each says
something about one object.

Nothing runs when a window closes, so the summary is written lazily: by the
caller's first refusal in a later window (for the window before it), and for
windows still open at shutdown by the service's graceful stop. The counter, not
the summary, is what a crash cannot lose; a summary lost with a crash is the
accepted cost. Rejected: a background timer writing summaries (a second writer
under the chain lock for a convenience).

## `DELETE /v1/originals/{document_id}`

Destroys every `document_keys` row of the document and evicts them from the
unwrap cache (crypto-shredding, ADR-0008). 200 `{"destroyed": n}`; idempotent
(n = 0 the second time). A key-lifecycle event records the count. After it,
`open` answers 404.

## `DELETE /v1/documents/{document_id}`

Under lock 1: destroy the document's keys (as above), delete its
`document_tokens` rows, delete every `pii_mappings` row whose token no other
document is registered for, delete every grant scoped to the document
(`grants.document_id` = the id, as `deletion.py` does in wordsworth today),
and set `known_documents.deleted_at` (the row keeps id and domain; no value,
no token). 200 `{"keys": n, "tokens": n, "mappings": n, "grants": n}`. An
unknown or already tombstoned document gives 200 with zeros, and its scoped
grants are deleted all the same. Audit: `event = "delete_document"` with the
counts; the grant deletions also go to `key_lifecycle_events`, as a grant
change does today.

Deleting the scoped grants keeps a promise of reveal-api: the former recipient
of a grant on a deleted document gets the uniform 403, not 410. Only a grant
that survives the deletion (unscoped where allowed, or under a global role)
covers a deleted document and hears 410.

## Volume

The metrics are mounted at `GET /v1/metrics`, so the existing
`ServiceTokenMiddleware` (prefix `/v1/`) covers them with no change to the
middleware: 401 without a token, no values, no document ids in the output. The
caller labels and purposes they expose say who opens how much, which is not for
anyone who can reach the port. Rejected: keeping `/metrics` at the root and
widening the middleware to cover it (a second path rule in the one component
whose job is to fail closed, and an exemption list that can silently drift);
an open `/metrics` guarded by network policy alone (the NetworkPolicy is not
there yet).

The route stays exempt from rate limiting, so monitoring is never refused:
`rate_limit.EXEMPT_PATHS` (today `{"/health", "/metrics"}`) gains `/v1/metrics`,
and `tests/test_rate_limit.py` is updated with it. The open-rate limit above is
per caller on `open` only and does not touch it. The scraper in the homelab
manifest is pointed at `/v1/metrics` and gets a service token of its own. It exposes
`keyservice_opens_total{service_caller, purpose}` and
`keyservice_open_refusals_total{service_caller, reason}`, so an alert on open
volume can be set. The alert rule itself belongs to the homelab manifest and
is not built in any of the key-service changes; until it exists, "alerting on
volume" (ADR-0009) is a counter nobody watches.

## Known residuals

Written into ADR-0009's threat model, which already carries all three as
residuals; the task extends those rows (the metrics now behind the service
token, the coarser audit of 429s, the batch cap) and does not add parallel
ones:

- `pseudonymise` turns any value into its token for whoever holds a service
  token, so a compromised wordsworth can confirm whether a guessed value
  occurs in its own index. Audited; not prevented, because ingest needs it.
- At the default rate a service caller can open about 170 000 originals a day
  (120 a minute). Audited and counted; bounded, not prevented.
- The service credential alone can crypto-shred any document
  (`DELETE /v1/originals`, `DELETE /v1/documents`): no person is asked.
  Audited; recovery is only from a backup of the service database taken
  before.
