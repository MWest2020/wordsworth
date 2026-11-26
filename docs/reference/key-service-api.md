---
status: draft
last_reviewed: 2026-11-26
---

# Key service — API reference

This is the key service's own API (ADR-0009), a different process and
database from wordsworth's. See [the how-to](../how-to/key-service.md) for
deployment, its database and failure modes.

In this change (`key-service-skeleton`) the surface is deliberately minimal:
the process boundary and its authentication, nothing else yet.
`key-service-vault` and `key-service-reveal` add the endpoints below the
`/v1` prefix.

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

## Not in this change

- Every key, mapping, token-registry and reveal operation — see
  `key-service-vault` and `key-service-reveal`.
- `POST /v1/export` — see `key-export-escrow`.
