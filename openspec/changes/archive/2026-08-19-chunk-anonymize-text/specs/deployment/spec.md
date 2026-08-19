## ADDED Requirements

### Requirement: Bounded GLiNER input via chunking

The anonymization driver SHALL bound the amount of text sent to the
OpenAnonymiser (GLiNER) service in a single call by splitting long text into
chunks, redacting each, and reassembling the result, so that a long document
cannot exceed the service's memory. The reassembled text SHALL be identical to
redacting the whole text except at chunk boundaries, and entity counts SHALL be
the sum across chunks. The chunk size SHALL be configurable.

#### Scenario: A long document is chunked and reassembled

- **WHEN** a document longer than the chunk size is anonymized
- **THEN** it is redacted in multiple bounded calls and the reassembled text is
  the concatenation of the redacted chunks, with counts summed

#### Scenario: Short documents are a single call

- **WHEN** a document is within the chunk size
- **THEN** it is anonymized in a single call (no behavioural change)
