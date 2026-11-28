# Design

The copy runs with wordsworth in maintenance for writes (ingest and grant
changes paused; search and the console stay up), so the copied state is
consistent. Verification is the gate: a mismatch aborts, leaves wordsworth on
the old drivers, and reports counts. The verification never prints a value: it
compares decryptions in memory and reports equal/unequal counts.

## Amended 2026-11-28 (architect FAIL on #559)

### The seam

`KeyProvider.key(key_id) -> Key(material)` and `MappingStore.get(token)` hand
key material and ciphertext to the caller. A service driver cannot implement
them: it must never return either (`key-service-pseudonymise`, "Only reveal
returns a clear value"). So **neither is the shared interface.** They remain
what the in-process driver uses internally, and the service never needs them
from wordsworth.

The shared interface is one level up, at the operations wordsworth asks of a
key authority, each the same call the service already exposes:

- `pseudonymise(document_id, domain, items[type, value]) -> tokens`
- `open_original(document_id, purpose) -> plaintext` (subject to the
  open-limits rate limit)
- `delete_document(document_id)`

The in-process driver implements these on `Pseudonymizer`, `DurableKeyProvider`
and `PostgresMappingStore`; the service driver implements them as calls to
`/v1/...`. The contract tests are written against these operations and run
against both drivers, which makes them the proof that the switch changes no
behaviour. Reveal (`decide`, `reveal`) is not in this interface until its
switch is decided. Names and signatures beyond these operations are the seam
change's to fix in its own design.

Rejected: widening `KeyProvider` and `MappingStore` with service methods (a
driver that raises on half its interface is a fallback in disguise), and one
big interface including reveal now (it would pull the open question into the
seam).

### Three builds

One change carried the interface, the switch, a migration, a drop command and
the management endpoints; a builder would have had to guess the order. The
split: **seam** (reversible by construction, default unchanged), **switch**
(reversible by configuration), **drop** (not reversible, so last, gated by
Mark). Rejected: one change with phased tasks (one architect pass, one review,
and a failure anywhere blocks the safe parts).

### Shared code: tokens stay stable only while the vault moves intact

The service imports `Pseudonymizer` and `DurableKeyProvider` from wordsworth
(`keyservice/api_pseudonymise.py:16-17`). It is one implementation under two
processes, so a token is the same only if the service sees the same keys.
Moving the vault intact (same key ids, same material, same scopes) is therefore
a precondition of the switch, not a detail of the migration; a changed
`Pseudonymizer` changes both sides at once. Rejected: a second implementation in
the service (two token functions that must agree forever).

### Reveal stays out of the switch

The design default (a reveal needs a signed identity; #524) is a working
assumption only. The switch change leaves reveal's drivers, routes and the
reveal-api requirement untouched. Consequence: wordsworth still holds key
material for reveal after the switch, so "no key in wordsworth" and the drop
of the old tables wait for reveal's own change.

### Carried over from the architect FAIL on `key-service-skeleton` (#522)

- **The registry is copied once, then the service's.** The copy trusts
  wordsworth's `document_pseudonyms` at that moment (ADR-0009 residual) and
  keeps its provenance: `minted` rows become `copied_minted`, `backfilled`
  rows `copied_backfilled` (those were read off stored text after the fact
  and were already less certain than minted ones). The copy is complete or it
  aborts: every token in every live document's current anonymized text must
  be in the copied registry for that document, else the cutover stops, names
  the count of missing pairs (never a value) and leaves the old drivers
  active. After the switch only the service's `pseudonymise` registers
  tokens. wordsworth
  may keep `document_pseudonyms` as its own copy for what is not a reveal
  (console type counts, `measure_combinations`, `reprocess_counts`, deletion
  counts); no reveal reads it.
- **Every document's domain is copied** from wordsworth's `register` audit
  record into `known_documents`, so a reveal judges the same domain as before;
  the verification compares them.
- **Decryption outside reveal.** `pdf_redaction._clear_values` decrypts
  mappings to build a box map. After the switch of pseudonymise wordsworth
  should hold no key, and no route of the service may return a clear mapping
  value to the service credential without a person
  (`key-service-pseudonymise`, "Only reveal returns a clear value"). So the box
  map is built from the values while they are in memory during processing
  (they come from the opened original and are sent to `pseudonymise`);
  rebuilding a box map later means reprocessing from the original. How exactly
  is the switch change's to settle; a decrypting route is ruled out.
- **Audit.** wordsworth's historic `deanonymize` records stay in its document
  chain (they hold tokens, no value, and moving them would break the chain).
  New reveals are recorded in the service's `access_audit`, with a
  cross-reference record in wordsworth's chain (`key-service-reveal`).
