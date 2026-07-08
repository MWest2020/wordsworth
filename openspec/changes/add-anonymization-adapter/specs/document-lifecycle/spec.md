## MODIFIED Requirements

### Requirement: Stub downstream transitions

The `index` transition SHALL exist and produce an audit record while performing
no domain work; its real behaviour is delivered by a later change. The `extract`
and `anonymize` transitions are no longer stubs — see "Text extraction" and
"Anonymization step".

#### Scenario: Index remains a stub

- **WHEN** the index step runs on an `anonymized` document
- **THEN** the document moves to `indexed` and an audit record is written, with
  no indexing performed

## ADDED Requirements

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
