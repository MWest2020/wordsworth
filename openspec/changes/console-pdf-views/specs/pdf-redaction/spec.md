## ADDED Requirements

### Requirement: The document page offers the PDF views

The console document page SHALL link the redacted PDF when the document has a
usable box map and SHALL state why not otherwise. For each active grant it SHALL
offer the reveal PDF through the same gates as the API.

#### Scenario: A redacted PDF exists

- **WHEN** an operator opens a document with a box map
- **THEN** the page links the redacted PDF

#### Scenario: No box map yet

- **WHEN** an operator opens a document without a box map
- **THEN** the page says the redacted PDF is not available and why
