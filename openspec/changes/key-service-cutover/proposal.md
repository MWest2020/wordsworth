# key-service-cutover

## Why

ADR-0009 migration step 2: wordsworth uses the key service, and the keys,
mappings, roles, groups, grants and their audit move into its database.

## What changes

- wordsworth's key, mapping, document-key and reveal drivers switch to the
  service's API (configuration), keeping the old in-process drivers available
  for rollback.
- A migration copies the key vault, document keys, mappings, roles, group
  mappings, grants and the reveal/key-lifecycle streams into the service's
  database, verified: row counts per table; every mapping decrypts to the same
  value under the moved keys; a fixed sample of reveals returns identical
  results before and after; every original opens.
- After a verification window (configurable, default 7 days) a separate
  command drops the old tables; until then rollback is switching the drivers
  back.

## Depends on

`key-service-skeleton`, `originals-encrypted-ingest` (with the changes before
it; they replaced `originals-envelope-encryption`),
`keycloak-groups-to-roles`.
