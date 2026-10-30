# key-service-skeleton

## Why

ADR-0009 (accepted 2026-10-30): one service holds the keys, the encrypted
values and the reveal decision; the rest of wordsworth sees tokens only. This
change builds that service without sending it traffic, so the cutover is a
separate, reversible step.

## What changes

- A new entrypoint and deployment, `wordsworth-keyservice`, in the same
  repository and image family, with its own database (separate Postgres
  database and role) and its own configuration.
- The `/v1` API of ADR-0009: `pseudonymise`, `reveal`, `originals/{id}/seal`,
  `originals/{id}/open`, `DELETE originals/{id}`, implemented over the existing
  modules (key provider, mapping store, grants, roles, document keys) but on
  the service's own database.
- Service-to-service authentication (a service token, mutual TLS later);
  callers' identities as the verified assertion, checked by the service itself.
- Every `open` audited with its purpose; a rate limit per service caller.

## Out of scope

Traffic from wordsworth and moving data (that is `key-service-cutover`).
