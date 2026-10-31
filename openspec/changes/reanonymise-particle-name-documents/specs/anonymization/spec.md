## ADDED Requirements

### Requirement: Re-anonymisation after a detection change is checked by counts only

When documents are re-anonymised because of a detection change, the system SHALL
log, per document, the number of detected entities per type before and after.
The check SHALL NOT log, print or write a detected value, the text around it, or
an offset.

#### Scenario: Counts before and after are logged

- **WHEN** a document is re-anonymised through the reprocess path
- **THEN** the number of detected entities per type before and after is logged
  for that document

#### Scenario: The check logs no value

- **WHEN** the check completes for a document that holds a detected name
- **THEN** its output and logs contain counts per type and no detected value,
  text or offset
