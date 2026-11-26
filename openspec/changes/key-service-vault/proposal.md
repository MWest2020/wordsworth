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
- Open counts as metrics, so an alert on volume can be set (the alert itself
  is a homelab follow-up).
- The service's own audit stream (`access_audit`) for all of the above.
- Docs: these endpoints in `docs/reference/key-service-api.md`, the rate limit
  and purposes in `docs/how-to/key-service.md`.

## Out of scope

Reveal and identity (`key-service-reveal`), traffic from wordsworth and moving
data (`key-service-cutover`), export (`key-export-escrow`).

## Depends on

`key-service-skeleton` (process, settings, schema, service token).
