## ADDED Requirements

### Requirement: Bounded backend concurrency

The service SHALL bound the number of concurrent calls it makes to the
memory-heavy backends — the OpenAnonymiser anonymization service and the Ollama
embedder — so that concurrent ingest callers cannot exceed those backends'
capacity. The limits SHALL be configurable. Exceeding the limit SHALL cause
callers to wait for a slot, not to fan out unbounded requests at the backend.
This SHALL NOT change the anonymize step's behaviour or output.

#### Scenario: Concurrent ingests do not exceed the anonymizer limit

- **WHEN** more ingest requests are in flight than the configured anonymize
  concurrency
- **THEN** no more than that many anonymize calls run against the OpenAnonymiser
  service at once; the rest wait for a slot

#### Scenario: Anonymize behaviour is unchanged

- **WHEN** a document is anonymized under the concurrency limiter
- **THEN** the redaction result and fail-hard behaviour are identical to running
  it without the limiter
