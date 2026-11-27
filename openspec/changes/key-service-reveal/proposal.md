# key-service-reveal

## Why

ADR-0009, build C of three (split out of `key-service-skeleton` after the
architect's FAIL on #522). The key service decides and performs reveals, so
that wordsworth's process and its service credential cannot reveal a value
without a user entitled to it. Three properties must survive the move across a
process boundary:

- the grant is decided before any document fact is read, and every caller it
  does not cover gets one and the same refusal (reveal-authorize-first,
  #487/#518);
- only tokens that belong to the document are revealed, decided from the
  service's own registry (ADR-0009, amended 2026-11-26);
- the person is identified by a signed assertion the service verifies itself,
  separate from the calling service's token.

## What changes

- `POST /v1/reveal/decide`: is this caller covered for this document, and for
  which types. Decrypts nothing and writes nothing.
- `POST /v1/reveal`: decides again, from scratch, and reveals the requested
  tokens that are registered for the document and of an authorised type;
  audits; returns values (text view) or only the resolved tokens (PDF view).
- The service verifies the person's assertion (issuer, signature, audience,
  validity) with wordsworth's `Verifier` code under its own configuration.
- The service's grants, roles and the admin role, read by the decision (rows
  only; the management endpoints come with `key-service-cutover`).
- The full contract, including what wordsworth does on its side of the
  boundary and in which order, is in `design.md`; wordsworth's side is built in
  `key-service-cutover`.
- Docs: the two endpoints in `docs/reference/key-service-api.md`; identity
  configuration and the audience in `docs/how-to/key-service.md`.

## Out of scope

wordsworth calling these endpoints (`key-service-cutover`); search on a value
(`search-by-value`); export (`key-export-escrow`).

## Depends on

`key-service-pseudonymise` (the registry, the known-documents table, the
mapping store and the audit stream) and `key-service-delete` (scoped grants
deleted with their document); both from the split of key-service-vault.
