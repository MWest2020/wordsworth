## ADDED Requirements

### Requirement: A locate miss is diagnosed with counts and a cause class only

The system SHALL provide a diagnostic for documents in `value-not-located` that
reports, per document and PII type, the number of occurrences in the anonymised
text, the number of whole-word matches in the positioned text, and a cause class
from a closed list. The diagnostic SHALL NOT output a value, a page text or a
context around a value.

#### Scenario: The diagnostic holds no value

- **WHEN** the diagnostic runs over a document with a `value-not-located`
- **THEN** its output has the document, the PII type, the two counts and a
  cause class, and none of the detected values nor any page text

### Requirement: A document with flat boxes is rebuilt, never served flat

A box map whose boxes have no surface SHALL be replaced by `reanonymize` with a
box map built from `char_box`. Until then the endpoints SHALL keep answering 409
`box map unusable`.

#### Scenario: A flat box map is rebuilt

- **WHEN** `reanonymize` runs for a document whose box map has a box without
  surface
- **THEN** the new box map has surface on every box and `GET redacted.pdf`
  answers 200

#### Scenario: A flat box map is not served

- **WHEN** a document still has a box without surface
- **THEN** the endpoint answers 409 and no PDF
