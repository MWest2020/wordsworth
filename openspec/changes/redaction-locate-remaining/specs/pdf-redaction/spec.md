## ADDED Requirements

### Requirement: The reprocess report counts remaining misses by type

The reprocess report SHALL list the `value-not-located` outcomes grouped by PII
type, with the number of documents and the located-of-occurrences counts per
type. The report, and any module added for it, SHALL log and output only the
type, the length and counts, never a value, a page text or a context around a
value.

#### Scenario: The report is grouped by type

- **WHEN** a reprocess run hits `value-not-located` for documents of several
  PII types
- **THEN** the report names each type with its document count and counts, and
  none of the detected values nor any page text

#### Scenario: A miss still fails closed

- **WHEN** a value cannot be located
- **THEN** no redacted PDF is served for that document and the report lists it
