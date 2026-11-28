# key-service-cutover-switch

## Why

Split from `key-service-cutover` (ADR-0009 migration step 2). The architect
failed that change twice (#559, #561): "the change is several builds in one and
a builder would have to guess". This is the second of three builds: the switch
only. The seam comes first (`key-service-cutover-seam`), the drop of the old
tables last (`key-service-cutover-drop`).

## What changes

- Pseudonymise, originals, open-limits and delete go to the key service
  through the service driver of the seam. The in-process drivers stay in the
  code and the old tables stay in the database, so rollback is configuration.
- A migration copies the key vault, document keys, mappings, the token registry
  (`document_pseudonyms` → `document_tokens`, provenance kept as
  `copied_minted` / `copied_backfilled`, complete or aborted), every document's
  id and domain (→ `known_documents`, tombstones for deleted ones), roles,
  group mappings, grants and the key-lifecycle stream into the service's
  database. It is verified (row counts per table; every mapping decrypts to the
  same value under the moved keys; every original opens) and aborts on any
  mismatch, leaving the old drivers active. It never prints a value.
- The box map no longer needs a decrypting route
  (`pdf_redaction._clear_values`): it is built from the values while they are in
  memory during processing.
- The service's management endpoints for roles, group mappings and grants,
  called by wordsworth's grant and role routes and the console.
- **Reveal is not touched.** Its routes, driver, statuses and authorisation are
  the same before and after. This is a working assumption, not an answer to
  #524: the default is that reveal needs a signed identity, applied in a
  separate change after Mark answers.

## Open questions

- **Reveal callers without a signed assertion (#524, Mark).** Can the console
  forward a signed identity? If not, every console reveal returns 403 once
  reveal is switched. Default: reveal needs a signed identity, in its own
  change; this change leaves reveal alone.
- **Who signs the sample reveals in the verification.** The service's reveal
  takes a signed person, and reveal stays in-process here. The sample-reveal
  comparison is therefore not part of this change's verification. Default: left
  out until reveal's change decides who signs.

## Depends on

`key-service-cutover-seam` (must be archived first; it holds the shared
interface, driver selection and the token-stability pin), plus the changes
already archived: `key-service-skeleton`, `-pseudonymise`, `-originals`,
`-open-limits`, `-delete`, `-reveal`, `originals-ingest-switch`,
`keycloak-groups-to-roles`.
