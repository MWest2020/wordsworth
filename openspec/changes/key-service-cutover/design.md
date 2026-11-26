# Design

The copy runs with wordsworth in maintenance for writes (ingest and grant
changes paused; search and the console stay up), so the copied state is
consistent. Verification is the gate: a mismatch aborts, leaves wordsworth on
the old drivers, and reports counts. The verification never prints a value: it
compares decryptions in memory and reports equal/unequal counts.

## Added 2026-11-26 (architect FAIL on `key-service-skeleton`, #522)

These follow from ADR-0009's amendment and must be settled in this change
before it is built; they are written here so its own architect pass starts
from them.

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
- **Reveal callers without a signed assertion.** API-key callers, the console
  cookie and the authentication-off mode carry no assertion the service can
  verify. Default (a question to Mark, #524): after the switch
  they cannot reveal and get 403 `reveal needs a signed identity`; machine
  clients use a client-credentials token from the identity provider. This
  changes the reveal-api requirement "Without caller authentication nothing
  changes", so this change's spec must modify that requirement.
- **Decryption outside reveal.** `pdf_redaction._clear_values` decrypts
  mappings to build a box map. After the switch wordsworth holds no key, and
  no route of the service may return a clear mapping value to the service
  credential without a person (`key-service-vault`, "Only reveal returns a
  clear value"). So the box map is built from the values while they are in
  memory during processing (they come from the opened original and are sent
  to `pseudonymise`); rebuilding a box map later means reprocessing from the
  original. How exactly is this change's to settle; a decrypting route is
  ruled out.
- **Audit.** wordsworth's historic `deanonymize` records stay in its document
  chain (they hold tokens, no value, and moving them would break the chain).
  New reveals are recorded in the service's `access_audit`, with a
  cross-reference record in wordsworth's chain (`key-service-reveal`).

