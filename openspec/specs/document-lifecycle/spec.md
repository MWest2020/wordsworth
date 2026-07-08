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

### Requirement: Stub downstream transitions

The `extract`, `anonymize`, and `index` transitions SHALL exist and produce
audit records in this change, while performing no domain work; their real
behavior is delivered by later changes.

#### Scenario: Stub transition records but does not transform

- **WHEN** the `extract` stub runs on an `extractable` document
- **THEN** the document moves to `extracted` and an audit record is written,
  with no text extraction performed

