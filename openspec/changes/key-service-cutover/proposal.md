# key-service-cutover

## Why

ADR-0009 migration step 2: wordsworth uses the key service, and the keys,
mappings, roles, groups, grants and their audit move into its database.

## What changes

- wordsworth's key, mapping, document-key and reveal drivers switch to the
  service's API (configuration), keeping the old in-process drivers available
  for rollback.
- A migration copies the key vault, document keys, mappings, the token
  registry (`document_pseudonyms` → `document_tokens`, provenance kept as
  `copied_minted` / `copied_backfilled`, complete or aborted),
  every document's id and domain (→ `known_documents`, tombstones for deleted
  ones), roles, group mappings, grants and the key-lifecycle stream into the
  service's database, verified: row counts per table; every mapping decrypts
  to the same value under the moved keys; a fixed sample of reveals returns
  identical results before and after; every original opens.
- wordsworth's reveal routes follow the order and the status mapping of
  `key-service-reveal` ("Order on wordsworth's side"); a document deletion
  calls `DELETE /v1/documents/{id}`.
- The service's management endpoints for roles, group mappings and grants
  (ADR-0009: "managed through its API"); wordsworth's grant and role routes
  and the console call them.
- After a verification window (configurable, default 7 days) a separate
  command drops the old tables; until then rollback is switching the drivers
  back.

## Depends on

`key-service-skeleton`, `key-service-vault`, `key-service-reveal`, `originals-ingest-switch` (with the changes before
it; they replaced `originals-envelope-encryption`),
`keycloak-groups-to-roles`.
