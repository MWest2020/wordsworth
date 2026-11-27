# key-service-open-limits

## Why

ADR-0009, build B, third of four (the split of `key-service-vault`, see
`key-service-pseudonymise`). ADR-0009 promises that every open of an original
is rate-limited per calling service and counted, so that a credential holder
who opens everything is bounded and visible. This change adds that to the
`open` of `key-service-originals`: the per-caller limit, an audit of refusals
that does not turn a flood into a flood of chained writes, one home for the
state only the service has, and the metrics behind the service token.

## What changes

- A token bucket per service caller on `POST /v1/originals/{id}/open`
  (`KEYSERVICE_OPEN_RATE_PER_MINUTE`, default 120;
  `KEYSERVICE_OPEN_BURST`, default 30), checked inside the route after the
  purpose: 401, then 422, then 429 with `Retry-After`.
- 429s audited once per caller per 60-second window, plus one
  `open_refused_summary` with the window's count, written lazily.
- `service_state`, the one table for state that only the service has and that
  is neither copied from wordsworth nor derived from `access_audit`: the
  refusal counters, the bucket and the refusal window. Its own drift test next
  to `tests/keyservice/test_drift.py`. The service's `rate_limit_buckets`
  stops being a copied table and is removed.
- `GET /v1/metrics` behind the service token: opens per caller and purpose
  (derived from `access_audit`) and refusals per caller and reason (from
  `service_state`). Never rate-limited, by construction.
- ADR-0009: the open-rate residual extended with the metrics behind the
  service token and the coarser audit of 429s.
- Docs: the limit, its defaults, the 429 audit and `/v1/metrics` in
  `docs/reference/key-service-api.md` and `docs/how-to/key-service.md`.

## Out of scope

The alert on open volume (the homelab manifest; none of the key-service
changes builds it), the scraper's service token in the homelab manifest (a
homelab PR, named in the how-to), deletion (`key-service-delete`).

## Next

`key-service-delete`

## Depends on

`key-service-originals` (the open route and its audit records).
