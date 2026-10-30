## ADDED Requirements

### Requirement: A value that survives replacement is reported without the value

When a detected value is still present after replacement, the system SHALL
refuse to emit the text and SHALL raise `AnonymizationInvariantError` with code
`waarde-overleefde-vervanging`. The error, the logs and the audit trail SHALL
carry only the PII type, the length, the counts and the word count of the value,
never the value.

#### Scenario: The text is refused

- **WHEN** a detected value is still in the text after replacement
- **THEN** the error is raised, no anonymised text is emitted, and the error
  carries type, length and counts only

#### Scenario: The error is not retried as transient

- **WHEN** the error is raised for a document
- **THEN** the document counts as `failed`, not `retryable`
