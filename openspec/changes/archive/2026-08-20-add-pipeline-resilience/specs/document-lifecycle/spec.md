## ADDED Requirements

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
