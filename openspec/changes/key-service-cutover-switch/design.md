# Design

The copy runs with wordsworth in maintenance for writes (ingest and grant
changes paused; search and the console stay up), so the copied state is
consistent. Verification is the gate: a mismatch aborts, leaves wordsworth on
the old drivers, and reports counts. It compares decryptions in memory and
reports equal/unequal counts, never a value.

## Reversible by configuration

The in-process drivers and old tables stay. Rollback is setting the drivers back
to in-process, inside the verification window. Rejected: removing the old path
now (not reversible; that is the drop change, gated by Mark).

## The registry is copied once, then the service's

The copy trusts wordsworth's `document_pseudonyms` at that moment (ADR-0009
residual) and keeps provenance: `minted` becomes `copied_minted`, `backfilled`
becomes `copied_backfilled`. The copy is complete or it aborts: every token in
every live document's current anonymized text must be in the copied registry for
that document, else the cutover stops, names the count of missing pairs and
leaves the old drivers active. After the switch only the service's
`pseudonymise` registers tokens. wordsworth may keep `document_pseudonyms` for
what is not a reveal (type counts, `measure_combinations`, `reprocess_counts`,
deletion counts).

## Every document's domain is copied

From wordsworth's `register` audit record into `known_documents`, and the
verification compares them.

## Tokens need the vault intact

The service imports `Pseudonymizer` and `DurableKeyProvider`, so a token is the
same only if the service holds the same keys. The pin test lives in the seam
change; here the migration copies the vault intact (same ids, material, scopes)
and verifies decryptions. Rejected: a second token implementation in the
service.

## Box map without a decrypting route

`pdf_redaction._clear_values` decrypts mappings. With the service driver the box
map is built from values in memory during processing (they come from the opened
original and are sent to `pseudonymise`); rebuilding one later means
reprocessing from the original. A decrypting route is ruled out (`key-service-
pseudonymise`, "Only reveal returns a clear value"). Exact mechanics are the
builder's to settle within that limit.

## Reveal stays out

Reveal keeps its in-process drivers, so wordsworth still holds key material for
reveal after this switch. "No key in wordsworth" and the drop of the old tables
therefore wait for reveal's change. Rejected: switching reveal here (it would
pull #524 into this build).

## Audit

wordsworth's historic `deanonymize` records stay in its chain (tokens, no value;
moving them would break the chain). New reveals are not recorded differently
here, since reveal is untouched.
