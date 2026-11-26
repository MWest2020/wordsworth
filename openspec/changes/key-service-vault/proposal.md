# key-service-vault

## Why

ADR-0009, build B of three (split out of `key-service-skeleton` after the
architect's FAIL on #522). The service gets the operations that need keys but
no person: turning values into tokens, sealing and opening originals, and
deleting a document's keys, tokens and orphaned values. Pseudonymise is also
where the token registry is filled, so that a later reveal decides from the
service's own record of which tokens belong to which document, not from a list
wordsworth supplies (ADR-0009, amended 2026-11-26).

## What changes

- `POST /v1/pseudonymise`: per document, with its domain, a batch of
  (type, value) in; tokens out. The service stores the encrypted value,
  registers each token for that document (`document_tokens`) and records the
  document's domain (`known_documents`) on first sight.
- `POST /v1/originals/{document_id}/seal` and `.../open`; every open carries a
  purpose from a fixed list, is audited and is rate-limited per calling
  service.
- `DELETE /v1/originals/{document_id}` (destroy the document's data keys) and
  `DELETE /v1/documents/{document_id}` (keys, registry rows, every mapping no
  other document is registered for, every grant scoped to the document; a
  tombstone keeps id and domain).
- No route here returns a clear value: only reveal does, and it needs a
  person (`key-service-reveal`).
- Open counts as metrics at `GET /v1/metrics` (behind the service token), so an alert on volume can be set (the alert itself
  is a homelab follow-up).
- The service's own audit stream (`access_audit`) for all of the above.
- Docs: these endpoints in `docs/reference/key-service-api.md`, the rate limit
  and purposes in `docs/how-to/key-service.md`.

## Amended after architect FAIL (wordsworth#532)

Decided: 429 refusals are counted in metrics and audited once per caller per
window; the pseudonymise batch is capped at 1 000 by default so lock 4781 is
not held long, with the hold time measured at cutover.

Amended again after the second architect FAIL (wordsworth#534): the metrics
move to `/v1/metrics`, so the existing service-token middleware covers them
and the route stays exempt from rate limiting; `docs/reference/lock-order.md`
is settled first with the key-lifecycle chain ordered before the audit chain;
the three residuals are written into ADR-0009's existing threat-model rows.

## Open questions

- The seven objectives in the architect's second verdict
  (`habitat/architect/key-service-vault-20261126-115709-26181`) were not read
  by this session (the branch could not be fetched). `design.md` resolves what
  the channel decided and the gaps found while amending (lock order, metrics,
  429 summary mechanics); an objective outside those is not yet resolved.
  Default: the build goes ahead on this change, and the architect's next
  verdict names any objective still open.

## Out of scope

Reveal and identity (`key-service-reveal`), traffic from wordsworth and moving
data (`key-service-cutover`), export (`key-export-escrow`).

## Depends on

`key-service-skeleton` (process, settings, schema, service token).
