---
status: draft
last_reviewed: 2026-11-26
---

# Runbook — the key service

ADR-0009: one service holds the keys, the encrypted values, the token
registry and the reveal decision; the rest of wordsworth sees tokens only.
This change (`key-service-skeleton`) ships the process boundary with **no
traffic** — nothing in wordsworth calls it yet. `key-service-vault` and
`key-service-reveal` fill it in.

## Deploying it

Same image as wordsworth, a different command (the Dockerfile is otherwise
unchanged):

```
wordsworth-keyservice-init   # once, before first start: creates the schema
wordsworth-keyservice        # serves /health and the (still empty) /v1 surface
```

It needs its own two environment variables, set independently of wordsworth's:

- `KEYSERVICE_DATABASE_URL` — required, no default. The `postgresql+psycopg://`
  scheme is required, same as wordsworth's own database URL.
- `KEYSERVICE_SERVICE_TOKENS` — `label:token` comma-separated pairs, one per
  calling service. A secret: inject via SOPS+age or OpenBao, never commit it.

## Its database and role

A **separate PostgreSQL database and role** from wordsworth's — the whole
point of the split is that wordsworth's role cannot read it. Create a
database and a role scoped to only that database before running
`wordsworth-keyservice-init`; do not reuse wordsworth's `wordsworth` role or
database.

The service's schema (`KeyServiceBase`) lives on its own `DeclarativeBase`,
disjoint from wordsworth's: no table it creates has a foreign key to a
wordsworth table, and no migration path exists yet. Until the cutover
(`key-service-cutover`) the database holds no data, so a schema change today
is made by dropping and recreating it, not by migrating.

## Refuses to start

At startup, and in `wordsworth-keyservice-init`, before touching or creating
anything:

1. **No `KEYSERVICE_DATABASE_URL`** (unset or empty) — refuses.
2. **The same database as `WORDSWORTH_DATABASE_URL`** (same host, port and
   database name, read straight from the environment, never through
   wordsworth's own settings) — refuses. Catches a copy-pasted configuration.
3. **A database that already holds `audit_records` or `document_texts`**
   (tables that exist only in wordsworth's schema) — refuses. Catches the
   real thing: pointing the service at wordsworth's database however the
   rest of the environment is configured.

Each refusal is an exception naming the rule, never a warning; the process
exits non-zero. There is no override.

## The service token

Every path under `/v1/` needs `Authorization: Bearer <token>`, checked
against `KEYSERVICE_SERVICE_TOKENS` in constant time. The matching label
becomes the caller recorded in later audit records. Unlike wordsworth's
optional, open-by-default API keys: **an empty token set refuses every
`/v1` call.** There is no "auth off" mode for this service — an open key
service is the one thing the process split exists to prevent.

`/health` needs no token. It says only that the process is up and its own
database is reachable — it does not say anything about `/v1`, which (in this
change) does nothing yet beyond refusing without a token.

## Failure modes

- **Process does not start**: one of the three refuse-to-start rules fired —
  check the exception message, it names which one.
- **`/health` returns 503**: the process is up but its database is not
  reachable (network, credentials, or the database is down). This is not a
  refuse-to-start rule; it can happen after a successful start.
- **Every `/v1` call returns 401**: either no token was sent, the token does
  not match any configured pair, or `KEYSERVICE_SERVICE_TOKENS` is empty
  (every call fails-closed in that case, by design).

## Not yet enforced

**The NetworkPolicy that admits only wordsworth's pods does not exist yet**
(a separate PR in `MWest2020/homelab`). Until it does, anything in the
cluster that holds a valid service token can reach this service. Treat the
token as the only boundary for now, and deploy the policy before relying on
network isolation.
