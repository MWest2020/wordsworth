# key-service-skeleton

## Why

ADR-0009 (accepted 2026-10-30, amended 2026-11-26): one service holds the keys,
the encrypted values, the token registry and the reveal decision; the rest of
wordsworth sees tokens only. The service ships without traffic first, so the
cutover is a separate, reversible step.

The first build of this change stopped at the architect (FAIL, #522): too big
for one build, no reveal contract, and a schema that could not live in a
database without wordsworth's tables. The service is therefore built in three
changes, in this order:

1. **`key-service-skeleton`** (this change): the process boundary.
2. `key-service-vault`: pseudonymise with the token registry, seal/open/delete
   of originals, document deletion, the service's audit stream and the rate
   limit on opens.
3. `key-service-reveal`: the reveal contract and the service's own identity
   verification.

How each finding of #522 is answered is in `design.md`.

## What changes

- A new entrypoint and deployment, `wordsworth-keyservice`, in the same
  repository and image (a different command), as the package
  `src/wordsworth/keyservice/`.
- Its own settings (`KEYSERVICE_*`), read by nothing in wordsworth; the service
  takes no value from wordsworth's `config.settings`.
- Its own SQLAlchemy metadata (`KeyServiceBase`), separate from wordsworth's
  `Base`, holding the service's whole schema (the tables the later two changes
  use, including the token registry `document_tokens` and the document → domain
  table `known_documents`), with no foreign key to any wordsworth table.
- Its own init entrypoint, `wordsworth-keyservice-init`, which creates that
  schema and nothing else, with the append-only trigger on its audit tables.
- It refuses to start against wordsworth's database.
- Service-to-service authentication: a service token per calling service,
  fail-closed (no configured token means every `/v1` call is refused).
- `GET /health`; no `/v1` endpoint does anything yet beyond authentication.
- Docs: how to deploy it, its database and its failure modes.

## Out of scope

- Every key, mapping, registry, originals and reveal operation
  (`key-service-vault`, `key-service-reveal`).
- Traffic from wordsworth and moving data (`key-service-cutover`).
- `POST /v1/export` (`key-export-escrow`), although ADR-0009 lists it in the
  same contract block.
- The NetworkPolicy that admits only wordsworth's pods (a separate PR in
  MWest2020/homelab).
