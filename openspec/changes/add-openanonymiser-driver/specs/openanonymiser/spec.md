## ADDED Requirements

### Requirement: OpenAnonymiser anonymization driver

An `OpenAnonymiserAnonymizer` SHALL implement the `Anonymizer` protocol,
delegating to OpenAnonymiser, and SHALL return the same `AnonymizationResult`
(text + per-type counts) so it is injectable into the pipeline with no pipeline
change. Replacement SHALL be irreversible.

#### Scenario: Injected as the de-identify driver

- **WHEN** the pipeline runs with the OpenAnonymiser driver injected
- **THEN** the anonymize step uses it and produces a de-identified text with counts

#### Scenario: Entity PII beyond the deterministic set is redacted

- **WHEN** text contains a personal name recognised by OpenAnonymiser
- **THEN** the name is replaced in the output

#### Scenario: Structured PII is not double-counted by the composite

- **WHEN** the composite driver processes text containing structured PII (e.g. an
  email) that both engines can recognise
- **THEN** the deterministic result is authoritative — the entity is replaced and
  counted once, its placeholder is preserved, and OpenAnonymiser does not
  re-process or re-count that type

### Requirement: Local inference, hard failure

Inference SHALL be local (no cloud). If anonymization fails, it SHALL raise — the
system SHALL NOT emit un-redacted text.

#### Scenario: Failure never leaks clear text

- **WHEN** the anonymization engine errors on a document
- **THEN** an error is raised and no un-redacted text is written or indexed
