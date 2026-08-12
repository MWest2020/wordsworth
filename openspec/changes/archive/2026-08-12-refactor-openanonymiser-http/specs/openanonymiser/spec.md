## MODIFIED Requirements

### Requirement: OpenAnonymiser anonymization driver

An `OpenAnonymiserAnonymizer` SHALL implement the `Anonymizer` protocol,
delegating entity-PII redaction to the OpenAnonymiser service **over HTTP**
(`POST {WORDSWORTH_OPENANONYMISER_URL}/api/v1/anonymize`), composed with the
deterministic detectors which run FIRST. It SHALL return the same
`AnonymizationResult` (text + per-type counts) so it is injectable into the
pipeline with no pipeline change. Replacement SHALL be irreversible. Wordsworth
SHALL NOT run the anonymization model in-process (no torch/spaCy/presidio pulled
into Wordsworth).

#### Scenario: Injected as the de-identify driver

- **WHEN** the pipeline runs with the OpenAnonymiser driver injected
- **THEN** the anonymize step uses it and produces a de-identified text with counts

#### Scenario: Entity PII beyond the deterministic set is redacted

- **WHEN** text contains a personal name recognised by OpenAnonymiser
- **THEN** the name is replaced in the output

### Requirement: Local inference, hard failure

Inference SHALL be local in the sovereign sense — no third-party cloud API. It
MAY run in a self-hosted, co-located service reached over the network (e.g. the
OpenAnonymiser service in the same cluster); calling that service is not a "cloud
call". If
anonymization fails — including the service being **unreachable**, timing out, or
returning a non-2xx response — it SHALL raise, and the system SHALL NOT emit
un-redacted text (no silent fallback to the un-redacted document).

#### Scenario: Failure never leaks clear text

- **WHEN** the anonymization engine errors on a document
- **THEN** an error is raised and no un-redacted text is written or indexed

#### Scenario: Unreachable service is a hard failure

- **WHEN** the OpenAnonymiser service is down or unreachable
- **THEN** the anonymize step raises rather than passing the document through
  un-redacted
