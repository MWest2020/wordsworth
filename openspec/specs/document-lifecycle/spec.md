# document-lifecycle Specification

## Purpose
TBD - created by archiving change add-pipeline-skeleton. Update Purpose after archive.
## Requirements
### Requirement: Document state machine

Each ingested document SHALL progress through an explicit, ordered set of
states: `registered`, `extractable`, `unprocessable_ocr`, `extracted`,
`anonymized`, `indexed`, and `failed`. A document SHALL be in exactly one state
at any time, and transitions SHALL follow only the defined edges.

#### Scenario: New document enters as registered

- **WHEN** a document is stored in object storage and its row is created
- **THEN** its state is `registered` and a `registered` audit record exists

#### Scenario: Undefined transition is rejected

- **WHEN** a transition is attempted that is not a defined edge for the current
  state
- **THEN** the transition is rejected and the document state is unchanged

### Requirement: Atomic transition and audit write

A state transition and its audit record SHALL be committed in a single database
transaction, so that no transition exists without its audit record and no audit
record exists without its transition.

#### Scenario: Crash mid-transition leaves no partial state

- **WHEN** a worker crashes after computing a transition but before commit
- **THEN** neither the new state nor its audit record is persisted, and the
  document remains in its prior state

### Requirement: Idempotent and resumable processing

Reprocessing a document SHALL resume from its last committed state, and a
transition whose target state has already been reached SHALL be a no-op.

#### Scenario: Resume after crash

- **WHEN** a batch run restarts and encounters a document already in
  `extractable`
- **THEN** profiling is not re-run and processing continues from `extractable`

### Requirement: Born-digital detection

The transition out of `registered` SHALL parse the document with pypdf, count
extractable characters per page, and classify the document as `extractable`
when characters-per-page is at or above the configured threshold, or
`unprocessable_ocr` when below it. The raw `chars`, `pages`, and `bytes` values
SHALL be recorded in the transition's audit payload.

#### Scenario: Born-digital document is extractable

- **WHEN** a PDF yields characters-per-page at or above the threshold
- **THEN** its state becomes `extractable` and the audit payload holds the raw
  chars, pages, and bytes

#### Scenario: Scanned document is unprocessable

- **WHEN** a PDF yields characters-per-page below the threshold
- **THEN** its state becomes `unprocessable_ocr` (terminal for the PoC) and the
  raw metric is recorded

#### Scenario: Parser crash fails loudly

- **WHEN** pypdf raises while parsing a document
- **THEN** the document transitions to `failed` with the error reason, and is
  NOT classified as `unprocessable_ocr`

### Requirement: Text extraction

The `extract` transition SHALL pull the document's text with pypdf and hold it in
memory for anonymization. Extraction SHALL NOT persist clear text. If extraction
raises, the document SHALL transition to `failed` (loud failure, no silent skip).

#### Scenario: Extractable document yields text

- **WHEN** the extract step runs on an `extractable` document
- **THEN** the document moves to `extracted`, an audit record is written, and no
  clear text is persisted

### Requirement: Anonymization step

The `anonymize` transition SHALL run the injected `Anonymizer` over the extracted
text, persist ONLY the anonymized text, and record the per-type replacement
counts in the transition's audit payload.

#### Scenario: Anonymized text is persisted with counts

- **WHEN** the anonymize step runs on an `extracted` document containing PII
- **THEN** the document moves to `anonymized`, the persisted text contains typed
  placeholders instead of the PII, and the audit payload records the counts

#### Scenario: Clean text anonymizes to itself

- **WHEN** the anonymize step runs on text with no detectable PII
- **THEN** the document still moves to `anonymized` with zero replacement counts

### Requirement: No clear text at rest

The system SHALL persist only anonymized text. On resume from `extracted`, the
text SHALL be re-derived from the source document rather than read from a
clear-text store.

#### Scenario: Only anonymized text is stored

- **WHEN** a document reaches `anonymized`
- **THEN** the only stored text for that document is the anonymized text

### Requirement: Indexing transition

The `anonymize → index → indexed` transition SHALL read the document's persisted
anonymized text, embed it with the injected `Embedder`, and push the text and its
vector to the injected `SearchIndex` before transitioning to `indexed`. Indexing
SHALL be idempotent (upsert by document id). A failed embedding or index failure
SHALL be treated as transient: it SHALL NOT mark the document `failed`, the run
SHALL NOT commit, and re-processing SHALL complete indexing. A null/zero vector
SHALL never be stored.

#### Scenario: Indexed document reaches the index with a vector

- **WHEN** the index step runs on an `anonymized` document
- **THEN** its anonymized text and embedding are present in the search index and
  the document moves to `indexed`

#### Scenario: Index or embedding outage is retryable, not a failure

- **WHEN** the embedder or the search index is unavailable during the index step
- **THEN** the document is not marked `failed`, nothing from that run commits, and
  re-processing with healthy backends completes indexing

### Requirement: Transient downstream failures are retried with bounded backoff

A transient failure of a downstream step (de-identify, embed, or index) SHALL be retried a bounded number of times with exponential backoff before it propagates, and permanent or logic errors SHALL NOT be retried. Retrying SHALL NOT weaken fail-hard: a document that cannot be de-identified is never indexed with clear PII.

#### Scenario: A brief blip self-heals

- **WHEN** a downstream step fails transiently fewer times than the retry budget
  and then succeeds
- **THEN** the document advances to INDEXED without operator intervention

#### Scenario: A persistent outage leaves the document resumable

- **WHEN** a downstream step keeps failing transiently past the retry budget
- **THEN** the error propagates, the document is NOT indexed and remains in its
  last resumable state, and no clear PII is persisted or indexed

#### Scenario: A permanent error is not retried

- **WHEN** a step raises a permanent/logic error
- **THEN** it propagates immediately with no retries

### Requirement: A batch continues past a failing document

Batch ingestion SHALL process every document even when one fails, and SHALL report each document's outcome, distinguishing a transient failure (retryable — the document stays resumable for a re-run) from a permanent failure.

#### Scenario: One document fails, the rest proceed

- **WHEN** a batch contains a document whose de-identify step is persistently down
  alongside documents that succeed
- **THEN** the successful documents are indexed, the failing one is reported
  retryable, and the batch is not aborted

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

