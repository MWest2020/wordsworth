## ADDED Requirements

### Requirement: Re-anonymisation after a detection change is checked by counts only

When documents are re-anonymised because of a detection change, the system SHALL
log, per document, the number of distinct pseudonyms per type in its stored
text before and after, and how many were added and removed, and SHALL return
the same numbers per document in the answer of the reprocess call. The line
SHALL be written only after the document's re-anonymisation is committed. The
check SHALL NOT log, print, return or write a detected value, a pseudonym
token, the text around it, or an offset.

#### Scenario: Counts before and after are logged

- **WHEN** a document is re-anonymised through the reprocess path
- **THEN** the number of distinct pseudonyms per type before and after is
  logged for that document

#### Scenario: The counts are in the answer

- **WHEN** a reprocess call re-anonymises a document
- **THEN** its answer holds, for that document, the counts per type before,
  after, added and removed, and no token or value

#### Scenario: A failed commit logs nothing

- **WHEN** the re-anonymisation of a document is not committed
- **THEN** no counts are logged or returned for it

#### Scenario: A replaced token is visible

- **WHEN** re-anonymising replaces one pseudonym of a type by another, so that
  the total for that type is unchanged
- **THEN** the log line for that document says one was added and one removed

#### Scenario: The check logs no value

- **WHEN** the check completes for a document that holds a detected name
- **THEN** its output and logs contain counts per type and no detected value,
  token, text or offset

#### Scenario: A document that was not re-anonymised

- **WHEN** a document is skipped or its re-anonymisation fails
- **THEN** no counts are logged for it and its outcome is reported as before
