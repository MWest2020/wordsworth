## ADDED Requirements

### Requirement: Re-de-identify a processed document in place

The system SHALL be able to re-run the de-identify step of an already-processed
document through the currently configured anonymizer, re-deriving the source text
from the object store by the document's key (never from a clear-text store),
re-embedding, and upserting the new de-identified text into the index and the
stored document text. The operation SHALL be idempotent and SHALL append an
audited access event; the index and stored text SHALL contain only de-identified
text. It SHALL be a no-op for a document that is not yet de-identified.

#### Scenario: Backfill an irreversibly-anonymized document to reversible

- **WHEN** a document indexed with the irreversible anonymizer is re-processed
  through the reversible driver
- **THEN** its stored and indexed text become keyed reversible pseudonyms, its
  mappings exist, an audit event records the re-processing (no clear values), the
  hash-chain still verifies, and no clear PII appears in the index

### Requirement: Re-de-identify is fail-safe

Re-processing SHALL compute, embed, and index the new de-identified text before
overwriting the stored text, so that a failure at any step leaves the existing
stored text and index entry unchanged and propagates the error. A batch
re-processing SHALL continue past a failing document, reporting it as retryable
(transient) or failed (permanent) without aborting the run.

#### Scenario: A failed re-process leaves the prior entry intact

- **WHEN** re-processing a document fails in the de-identify/embed/index step
- **THEN** the document's existing stored text and index entry are unchanged and
  the batch continues with the remaining documents
