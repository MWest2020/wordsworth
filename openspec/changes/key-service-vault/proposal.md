# key-service-vault

## Why

ADR-0009, build B of three (split out of `key-service-skeleton` after the
architect's FAIL on #522). The service gets the operations that need keys but
no person: turning values into tokens, sealing originals, and deleting a
document's keys, tokens and orphaned values. Pseudonymise is also where the
token registry is filled, so that a later reveal decides from the service's own
record of which tokens belong to which document, not from a list wordsworth
supplies (ADR-0009, amended 2026-11-26).

## What changes

- `POST /v1/pseudonymise`: per document, with its domain, a batch of
  (type, value) in; tokens out. The service stores the encrypted value,
  registers each token for that document (`document_tokens`) and records the
  document's domain (`known_documents`) on first sight. Capped at 1 000 items
  by default.
- `POST /v1/originals/{document_id}/seal`.
- `DELETE /v1/originals/{document_id}` (destroy the document's data keys) and
  `DELETE /v1/documents/{document_id}` (keys, registry rows, every mapping no
  other document is registered for, every grant scoped to the document; a
  tombstone keeps id and domain).
- No route here returns a clear value: only reveal does, and it needs a
  person (`key-service-reveal`).
- A new home for service-only state, `service_state`, with its own drift test
  next to `tests/keyservice/test_drift.py`. It will hold the open-refusal
  counter and the 429 window state (`key-service-open`); this change creates it.
  `rate_limit_buckets` stops being a table copied from wordsworth.
- The lock order of the service's database, written on
  `docs/reference/lock-order.md` first: key lifecycle before audit.
- `GET /v1/metrics` behind the service token, rendering the counters in
  `service_state`.
- ADR-0009: the three residuals extended, and a new risk line that `open`
  returns plaintext over HTTP on the wordsworth-to-service link.
- The service's own audit stream (`access_audit`) for all of the above.
- Docs: these endpoints in `docs/reference/key-service-api.md`, the residuals
  in `docs/how-to/key-service.md`.

## Split (architect, third FAIL, wordsworth#534)

The architect failed a third time: the change is too big for one build, and it
named six points where a builder would have to guess. Decided:

- `key-service-vault` keeps the token registry, `known_documents`, the lock
  order (key lifecycle before audit), `/v1/metrics` behind the service token,
  and the ADR-0009 residuals task.
- `POST /v1/originals/{document_id}/open`, with its batch cap of 1 000, the
  coarser 429 audit and the rate limiting, moves to a new change
  `key-service-open`, which depends on this one. That change is written by its
  own run; this one does not write it. Until it exists nothing here opens an
  original.
- Service-only state gets one home, `service_state` (see `design.md`). Neither
  the refusal counter (`keyservice_open_refusals_total`) nor the 429 window
  state (`rate_limit_buckets`) is derived from `access_audit`.
- The earlier decisions stay: 429s audited once per caller per window, the
  pseudonymise batch below 10 000, metrics at `/v1/metrics`.

## Open questions

- The architect's third verdict
  (`habitat/architect/key-service-vault-20261126-121433-19116`) could not be
  read: the branch is not on origin (`git fetch` finds no such ref), as with
  the two before it. Its six numbered points are resolved in `design.md` by
  this session, each with a rejected alternative, from the channel decision and
  from the repository; a point outside those is not resolved. Default: the
  build goes ahead on this change, and the architect's next verdict names any
  point still open.
- The `/v1/metrics` route here renders whatever counters `service_state`
  holds, and none exist before `key-service-open`. Whether the vault should
  count its own calls (pseudonymise, seal, delete) is not decided. Default: it
  does not; the route is tested with a counter the test writes itself.

## Out of scope

`open` and the rate limit (`key-service-open`), reveal and identity
(`key-service-reveal`), traffic from wordsworth and moving data
(`key-service-cutover`), export (`key-export-escrow`). `key-service-reveal` and
`key-service-cutover` still name `open` in their text; their wording follows
`key-service-open` when that is written.

## Depends on

`key-service-skeleton` (process, settings, schema, service token).
