# Design

All routes below sit behind the skeleton's service token (401 first, before
the body is parsed). The caller is a service (`service_caller`, the token's
label); no person is involved and no user assertion is read. Request logging
drops the body and the response of every route here: no value, original byte
or key byte reaches a log.

Modules (each ≤ 200 lines): `api_pseudonymise.py`, `api_originals.py` (seal and
delete; `key-service-open` adds `open` to it or to a sibling), `api_documents.py`,
`api_metrics.py`, `stores.py` (the service's mapping store, key vault and
document keys over `KeyServiceBase`, implementing the same protocols as
wordsworth's: `MappingStore`, `KeyProvider`, `DocumentKeys`' interface),
`audit.py`, `state.py` (`service_state`). The token derivation, normalisation
and encryption are wordsworth's own functions (`Pseudonymizer.pseudonym`,
`normalization`, `crypto`, `originals_envelope`), called with the service's
stores; nothing about how a token is made changes. The import rules of
`key-service-skeleton` ("Reuse and imports") apply: `document_keys.kek_name_for`
gets the domain → KEK mapping as an argument and `DocumentKeys` gets its cache
size and TTL from the service's settings (`KEYSERVICE_ORIGINALS_KEK`,
`KEYSERVICE_ORIGINALS_KEK_BY_DOMAIN`, `KEYSERVICE_DOCUMENT_KEY_CACHE_SIZE`,
`KEYSERVICE_KEY_CACHE_TTL`), wordsworth's call sites keeping their defaults;
the tests of this change run under the fixture that makes `config.settings`
raise.

## The split

The architect's third verdict (too big for one build) is met by moving `open`
out, because `open` is what drags in the purposes list, the rate limiter, the
429 audit mechanics and the refusal counter: four things that share nothing
with the registry. Rejected: moving `seal` and the deletes too (a smaller
vault, but then the registry has no deletion and `known_documents` no
tombstone, and the #465 twin cannot be tested here); keeping `open` and only
cutting the 429 audit (the other three stay). `key-service-open` depends on
this change: it needs the lock order, `service_state` and `/v1/metrics` below.

## Only reveal returns a clear value

No route of the service returns a clear mapping value to a calling service
without a verified person. The routes here return tokens, sealed bytes and
counts; the only route that returns mapping values is `/v1/reveal`
(`key-service-reveal`), and it needs a person's assertion and a grant. A later
need for clear values without a person (the box map, `key-service-cutover`) is
met from the values in memory during processing, not by a new route.

## Service-only state: `service_state`

State that only the service has and that is not a copy of a wordsworth table
and not derived from `access_audit` lives in one table, `service_state`:
`kind` text, `key` text, `counter` bigint NOT NULL default 0, `data` JSONB
NULL, `updated_at`; primary key (`kind`, `key`). `kind` is `counter` (a metric
such as `keyservice_open_refusals_total`, `key` the label set) or `rate_bucket`
(the 429 window state, what `rate_limit_buckets` was meant to hold, `key` the
caller label). `state.py` is the only module that writes it.

Why a table and not memory: a counter that restarts at zero on a crash hides
exactly the burst an investigation looks for. Why not derive it from
`access_audit`: the audit gets one record per window, not per refusal, so a
count rebuilt from it would be wrong by design. Rejected: keeping
`rate_limit_buckets` as a table copied from wordsworth's `RateLimitBucket` (it
is service state, not a mapping the cutover copies, and the copy would sit in
the drift test as if wordsworth's shape governed it); one table per kind (two
homes to keep out of the audit and out of wordsworth); an in-process counter
flushed at shutdown (a crash loses it).

The skeleton's schema table lists `rate_limit_buckets` as copied from
`RateLimitBucket`. That row goes: the service has no table of that name and
`RateLimitBucket` leaves `_COPIED_PAIRS` in `test_drift.py`. Wordsworth's own
`rate_limit_buckets` and `rate_limit_pg.py` are untouched.

A second test, `tests/keyservice/test_service_state_drift.py`, next to
`test_drift.py`, pins the shape and the boundary: `service_state` has exactly
the columns above; every table of `KeyServiceBase.metadata` is either in
`_COPIED_PAIRS`, one of the service's own tables (`known_documents`,
`document_tokens`, `access_audit`, `service_state`), and no table holds a
counter or window column outside `service_state`; `service_state` is absent
from wordsworth's metadata; and nothing in `state.py` reads `access_audit`.

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

One order inside the service's database, for every writer, written first on
`docs/reference/lock-order.md`:

1. the registry advisory lock (`pg_advisory_xact_lock(4781)`, the service's
   own key) — taken by `pseudonymise`, `seal` and `DELETE /v1/documents`;
2. the `known_documents` row;
3. `document_keys` rows, by `object_key`, `FOR UPDATE`;
4. `pii_mappings` rows, by token: inserted `ON CONFLICT DO NOTHING` by
   `pseudonymise`, `FOR UPDATE` by a deletion;
5. the `key_lifecycle_events` chain lock, advisory key **4783**, taken by a
   writer that records a key-lifecycle event;
6. the `access_audit` chain lock, advisory key 4782, last: the audit stays the
   terminal leaf, nothing is taken after it.

The key 4783 is fixed here, not left to the build: 4781 and 4782 are the
service's, 4783 is the next free one in the service's range (wordsworth's
are 4771 and 4772 and are another database).

`DELETE /v1/originals/{id}` and `DELETE /v1/documents/{id}` write both a
key-lifecycle event (destroyed keys, deleted grants) and an `access_audit`
record, so they take 5 then 6, in that order, in one transaction. Decided: put
key lifecycle before the audit. Rejected: audit before key lifecycle, which
would make the audit a non-terminal lock and every future lifecycle writer
reason about it; and two transactions (a lifecycle event, then the audit),
which leaves a destroyed key with no audit record if the second fails.
wordsworth's page describes the key-lifecycle chain (4772) as "never together
with 4771"; that sentence is about wordsworth's database, not this one, and
the page says so after this change.

`service_state` rows are updated by single statements (`INSERT ... ON CONFLICT
DO UPDATE`) and take no advisory lock; a writer holds no row lock of it while
waiting for any lock above. `key-service-open` takes its row after, and
independently of, lock 6 is released.

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

## `DELETE /v1/originals/{document_id}`

Destroys every `document_keys` row of the document and evicts them from the
unwrap cache (crypto-shredding, ADR-0008). 200 `{"destroyed": n}`; idempotent
(n = 0 the second time). A key-lifecycle event records the count. After it, a
sealed object of the document cannot be opened (`key-service-open` answers 404).

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

## `GET /v1/metrics`

Mounted at `/v1/metrics`, so the existing `ServiceTokenMiddleware` (prefix
`/v1/`) covers it with no change to the middleware: 401 without a token, no
values, no document ids in the output. It renders the `counter` rows of
`service_state` in Prometheus text format. The caller labels and purposes that
`key-service-open` adds say who opens how much, which is not for anyone who
can reach the port. Rejected: keeping `/metrics` at the root and widening the
middleware to cover it (a second path rule in the one component whose job is to
fail closed, and an exemption list that can silently drift); an open
`/metrics` guarded by network policy alone (the NetworkPolicy is not there
yet).

That the route is exempt from rate limiting, and the scraper's own service
token and manifest change, belong to `key-service-open`, which builds the
limiter. Until then there is no limiter to exempt it from. The alert on open
volume belongs to the homelab manifest and is built in none of the
key-service changes.

## Known residuals

Written into ADR-0009's threat model, which already carries the first three as
residuals; the task extends those rows and adds one risk line, and does not
add parallel ones:

- `pseudonymise` turns any value into its token for whoever holds a service
  token, so a compromised wordsworth can confirm whether a guessed value
  occurs in its own index. Audited; not prevented, because ingest needs it.
  The batch is capped (1 000 by default).
- At the default rate a service caller can open about 170 000 originals a day
  (120 a minute). Audited and counted; bounded, not prevented. The metrics are
  behind the service token; the audit of refused opens is coarser (one record
  per caller per window).
- The service credential alone can crypto-shred any document
  (`DELETE /v1/originals`, `DELETE /v1/documents`): no person is asked.
  Audited; recovery is only from a backup of the service database taken
  before.
- **The wire.** `open` returns the original in plaintext over HTTP on the
  link between wordsworth and the service, and `seal` receives it the same way.
  Whoever can read that link reads the originals in transit; the service's
  encryption at rest does not cover it. The link is a transport the deployment
  chooses (ADR-0009 names mutual TLS or a service token; the token alone does
  not encrypt). Not prevented by this change: it is a risk line, with the
  deployment's TLS as the mitigation. Rejected: leaving it out because the
  skeleton already says "mutual TLS or a service token", which reads as if the
  wire were covered.
