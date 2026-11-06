## ADDED Requirements

### Requirement: A long synthetic PDF corpus with known answers

The project SHALL provide a generator that writes a corpus of long synthetic PDF
documents with page-level ground truth for personal data and known answers for
search, built only from values that cannot belong to a real person.

#### Scenario: Gold matches the pages

- **WHEN** the generator writes a corpus
- **THEN** every planted value in `gold.jsonl` appears on the page it names in that document's extracted text, unless the page is listed as scanned

#### Scenario: Values cannot be anyone's

- **WHEN** the generator plants a BSN or an IBAN
- **THEN** the BSN starts with `9999` and passes the elfproef, and the IBAN uses a bank code that does not exist

#### Scenario: Reproducible

- **WHEN** the generator runs twice with the same seed and options
- **THEN** it writes identical files
