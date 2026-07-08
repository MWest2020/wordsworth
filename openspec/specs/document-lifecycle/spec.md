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
anonymized text and push it to the injected `SearchIndex` before transitioning to
`indexed`. Indexing SHALL be idempotent (upsert by document id). Index failure
SHALL be treated as transient: it SHALL NOT mark the document `failed`, the run
SHALL NOT commit, and re-processing SHALL complete indexing.

#### Scenario: Indexed document reaches the index

- **WHEN** the index step runs on an `anonymized` document
- **THEN** its anonymized text is present in the search index and the document
  moves to `indexed`

#### Scenario: Index outage is retryable, not a failure

- **WHEN** the search index is unavailable during the index step
- **THEN** the document is not marked `failed`, nothing from that run commits, and
  re-processing with a healthy index completes indexing

