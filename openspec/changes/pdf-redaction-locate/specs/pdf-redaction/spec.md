## MODIFIED Requirements

### Requirement: A value that cannot be located fails hard

For each token, when its count in the anonymised text exceeds the whole-word
matches of its value in the positioned text (`positioned_text`, pypdfium2), the
system SHALL write a `value-not-located` audit record and
`GET /documents/{id}/redacted.pdf` SHALL answer 409 with no PDF. There SHALL be
no fallback to a partly redacted PDF.

#### Scenario: A value cannot be found in the positioned text

- **WHEN** a value occurs twice in the pypdf text and once in the positioned text
- **THEN** a `value-not-located` audit record exists and the endpoint answers
  409 without a PDF

#### Scenario: A token occurs more often than its value is located

- **WHEN** a token occurs twice in the anonymised text and its value has one
  whole-word match in the positioned text
- **THEN** a `value-not-located` audit record exists and the endpoint answers 409
  without a PDF

## ADDED Requirements

### Requirement: Reprocess reports every value that could not be located

`POST /reprocess` SHALL list every `value-not-located` outcome in `problems`,
naming the document, the PII type and the counts, never the value.

#### Scenario: Reprocess reports a value-not-located

- **WHEN** a reprocess run hits `value-not-located` for a document
- **THEN** the response `problems` is non-empty and names that document
