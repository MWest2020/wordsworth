## ADDED Requirements

### Requirement: De-identified corpus ZIP export

The system SHALL export a ZIP archive containing one text entry per INDEXED
document, named by the document id, whose content is that document's stored
de-identified (anonymized/pseudonymised) text. The export SHALL contain only
de-identified text — never clear PII and never original document bytes — and
SHALL be filterable to a given subset of document ids. Documents without stored
de-identified text SHALL be skipped.

#### Scenario: ZIP holds only de-identified text for indexed documents

- **WHEN** the anonymized-docs export is requested
- **THEN** the archive has one `{document_id}.txt` entry per INDEXED document, each
  entry's content is that document's stored de-identified text, and no clear PII or
  original bytes appear

#### Scenario: Filter to a subset of documents

- **WHEN** the export is requested for a specific set of document ids
- **THEN** only those documents' de-identified texts are included

### Requirement: Ranking CSV export

The system SHALL export the ranking for a query as CSV (openable in a spreadsheet)
with a header row and one row per hit, in rank order, carrying de-identified
metadata only (rank, document id, score, object key) — never document text.

#### Scenario: CSV rows are in rank order

- **WHEN** a ranking export is requested for a query
- **THEN** the CSV has a header and one row per hit ordered by rank, each row
  identifying the document and its score, with no clear PII

### Requirement: Export CLI

The CLI SHALL provide commands to download the de-identified corpus ZIP and a
query ranking CSV to local files, resolving the API URL by the standard
precedence, using only the standard library.

#### Scenario: CLI writes the export to a file

- **WHEN** the operator runs the export docs or export ranking command
- **THEN** the client requests the corresponding export endpoint and writes the
  returned archive/CSV to the given output path
