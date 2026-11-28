# key-service-cutover

## Why

ADR-0009 migration step 2: wordsworth uses the key service, and the keys,
mappings, roles, groups, grants and their audit move into its database.

Amended 2026-11-28 after the architect's FAIL on #559: "the change is several
builds in one and a builder would have to guess". It is now one plan with three
ordered builds, a defined seam, and reveal left alone until Mark answers.

## What changes

The cutover is built as three changes, in this order. Each is proposed and
applied on its own, and the next does not start before the previous is archived.

1. **`key-service-cutover-seam`**: the interface both kinds of driver share,
   and configuration to select the driver, with contract tests run against
   both. The in-process driver stays the default; nothing in production
   changes.
2. **`key-service-cutover-switch`**: switches pseudonymise, originals,
   open-limits and delete to the service. The in-process drivers stay in the
   code and the old tables stay in the database, so rollback is configuration.
   Holds the migration (copy plus verification). It does not touch reveal.
3. **`key-service-cutover-drop`**: a separate command that drops the old tables
   after the verification window (configurable, default 7 days). Needs Mark's
   go-ahead before it is built or run.

What the whole cutover covers:

- A migration copies the key vault, document keys, mappings, the token
  registry (`document_pseudonyms` → `document_tokens`, provenance kept as
  `copied_minted` / `copied_backfilled`, complete or aborted),
  every document's id and domain (→ `known_documents`, tombstones for deleted
  ones), roles, group mappings, grants and the key-lifecycle stream into the
  service's database, verified: row counts per table; every mapping decrypts
  to the same value under the moved keys; a fixed sample of reveals returns
  identical results before and after; every original opens.
- A document deletion calls `DELETE /v1/documents/{id}`.
- The service's management endpoints for roles, group mappings and grants
  (ADR-0009: "managed through its API"); wordsworth's grant and role routes
  and the console call them.
- **The service shares code with wordsworth.** `Pseudonymizer` and
  `DurableKeyProvider` are imported by the service
  (`keyservice/api_pseudonymise.py:16-17`). A token is a function of the value
  and the key, so tokens stay stable across the switch only while the key vault
  moves intact. A test pins this (see tasks).
- Reveal is **not** part of the switch (open question below). The reveal routes
  keep their in-process driver. Their order and status mapping for a later
  switch are those of `key-service-reveal` ("Order on wordsworth's side"),
  archived in PR #560.

## Open questions

- **Reveal callers without a signed assertion (#524, Mark).** Working
  assumption, not a requirement: after a later switch of reveal, API-key
  callers, the console cookie and the authentication-off mode cannot reveal
  and get 403 `reveal needs a signed identity`; machine clients use a
  client-credentials token. Until Mark answers, `key-service-cutover-switch`
  must not touch reveal. Default: the assumption above, applied in a separate
  change after his answer. Feasibility check (a task): can the console's
  Keycloak session forward a raw assertion?
- **Dropping the old tables.** The in-process reveal needs the key vault and
  mappings, so the drop cannot run while reveal is in-process. It needs Mark's
  go-ahead and a switched reveal. Default: not built, not run.
- **Who signs the sample reveals in the migration's verification.** The
  service's reveal takes a signed person; the verification needs an identity
  for it. Not decided.
- **Architect findings on #559.** The amendment brief asked for the full
  findings, including the truncated first one. This amendment could not read
  them (no access to the issue from the run), so only the five points of the
  brief are folded in. Default: the architect re-runs on the amended change and
  anything it still finds is added.

## Depends on

`key-service-skeleton`, `key-service-pseudonymise`, `key-service-originals`,
`key-service-open-limits`, `key-service-delete`, `key-service-reveal` (merged in
PR #558; archive in PR #560, and this change's deltas apply against the
archived state), `originals-ingest-switch` (with the changes before
it; they replaced `originals-envelope-encryption`),
`keycloak-groups-to-roles`.
