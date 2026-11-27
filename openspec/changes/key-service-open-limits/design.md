# Design

This change's tests run under the fixture that makes `config.settings` raise,
against FakeTransit and the service's own test database.

## Service-only state: `service_state`

State that only the service has, that is not a copy of a wordsworth table and
not derived from `access_audit`, lives in one table, `service_state`:
`kind` text, `key` text, `counter` bigint NOT NULL default 0, `data` JSONB
NULL, `updated_at`; primary key (`kind`, `key`). `state.py` is the only module
that writes it. Kinds:

| `kind` | `key` | holds |
|---|---|---|
| `counter` | metric name and label set, e.g. `keyservice_open_refusals_total{caller="wordsworth",reason="rate"}` | `counter` |
| `rate_bucket` | caller label | `data`: tokens left, last refill time |
| `refusal_window` | caller label | `data`: window start, refusals in it; `counter` unused |

Why a table and not memory: a counter that restarts at zero on a crash hides
exactly the burst an investigation looks for, and the service runs more than
one replica (`2026-09-20-hoge-beschikbaarheid`), so per-process state would
make "once per caller per window" once per replica. Why not derive the
refusals from `access_audit`: the audit gets one record per window, not per
refusal, so a count rebuilt from it is wrong by design. Rejected: keeping
`rate_limit_buckets` as a table copied from wordsworth's `RateLimitBucket`
(it is service state, not a mapping the cutover copies, and a window column on
it fails `test_drift.py`); one table per kind (more homes to keep out of the
audit and out of wordsworth); an in-process counter flushed at shutdown (a
crash loses it, and replicas disagree).

Every write is one statement (`INSERT ... ON CONFLICT DO UPDATE ...
RETURNING`), computed with the database server's `now()`, never a replica's
clock. No advisory lock; a writer holds no `service_state` row while waiting
for any other lock, and writes it in its own short transaction after the
route's main transaction (and lock 4782) is released (the lock order of
`key-service-pseudonymise`). `state.py` takes an optional `now` argument
(default `now()` on the server) so a test can cross a window boundary.

The skeleton's schema lists `rate_limit_buckets` as copied from
`RateLimitBucket`. That row goes: the service's `RateLimitBucket` model is
removed and the pair leaves `_COPIED_PAIRS`. wordsworth's own
`rate_limit_buckets` and `rate_limit_pg.py` are untouched.

`tests/keyservice/test_service_state_drift.py` pins the shape and the
boundary: `service_state` has exactly the columns above; every table of
`KeyServiceBase.metadata` is either in `_COPIED_PAIRS` or one of the service's
own (`known_documents`, `document_tokens`, `access_audit`, `service_state`);
no other table has a column named like a counter or window (`counter`,
`count`, `tokens`, `window_start`, `refusals`); `service_state` is absent from
wordsworth's metadata; and `state.py` never names `access_audit`.

## The rate limit

A token bucket per service caller, keyed on the caller label, not the path,
held in the caller's `rate_bucket` row: `KEYSERVICE_OPEN_RATE_PER_MINUTE`
(default 120) refill, `KEYSERVICE_OPEN_BURST` (default 30) capacity. One
statement refills and takes a token and returns whether it was allowed and,
if not, the seconds until the next token (`Retry-After`).

The bucket is checked inside the `open` route, after the token middleware
and after the purpose and query are validated, so the order is 401, 422, 429,
then the rest of `key-service-originals`' table. The service mounts no
path-keyed limiter middleware; `open` is the only limited route. Rejected:
an ASGI limiter middleware (it would answer 429 before the 422 the design
promises, and it is a path rule that `/v1/metrics` would have to be exempted
from).

## The 429 audit

A 429 costs no hash-chained write per refusal: a caller hammering the route
would otherwise turn every refusal into a write under the chain lock (4782),
slowing the audit for everyone. Per refusal, in one statement on the caller's
`refusal_window` row: if the stored window start is the current 60-second
window, add one; otherwise start a new window at one and return the previous
window's start and count. Then:

- every refusal increments
  `keyservice_open_refusals_total{caller,reason="rate"}`;
- the refusal that starts a window (count 1) writes one `open_refused` record
  (`reason = "rate"`);
- when it also returned a previous window, it first writes that window's
  `open_refused_summary` (window start, count).

So the summary is written lazily, by the caller's first refusal in a later
window. A caller that is never refused again leaves its last window without a
summary; its count is still in the counter and in `/v1/metrics`. Because the
row is shared in the database, two replicas agree on which refusal starts a
window. Rejected: one record per refusal (the write amplification above); no
audit at all (a refused burst is the signal an investigation looks for); a
background timer or a shutdown hook writing summaries (a second writer under
the chain lock for a convenience, and a crash skips the hook anyway). The
other refusals of `open` (`no_key`, `unwrap`, `envelope`) stay one record
each: they are not caller-driven floods and each says something about one
object.

## `GET /v1/metrics`

Mounted at `/v1/metrics`, so the existing `ServiceTokenMiddleware` (prefix
`/v1/`) covers it with no change to the middleware: 401 without a token. It
renders, in Prometheus text format:

- `keyservice_opens_total{caller,purpose}`: counted from `access_audit`
  records with `event = "open"` at scrape time, the way wordsworth's
  `metrics.render_metrics` derives its numbers from the audit. Exact, and it
  survives a restart without a second write.
- `keyservice_open_refusals_total{caller,reason}`: the `counter` rows of
  `service_state`.

No value, document id or object key appears in the output. Who opens how much
is not for anyone who can reach the port, hence the token. Rejected: `/metrics`
at the root with a widened middleware (a second path rule in the one
component whose job is to fail closed); an open `/metrics` guarded by network
policy alone (the NetworkPolicy is not there yet). The route is never
rate-limited because nothing limits it: there is no limiter middleware. The
scraper needs its own service token; adding it to the homelab scrape config is
a homelab PR, which the how-to names. The alert on open volume belongs to the
homelab manifest and is built in none of the key-service changes.

## Modules

`state.py`, `limits.py` (the bucket and the 429 audit, called from the open
route), `api_metrics.py`. Each ≤ 200 lines.
