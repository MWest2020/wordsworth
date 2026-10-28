## ADDED Requirements

### Requirement: The over-detection baseline is recorded as counts, per type

The over-detection baseline SHALL be measured on the evaluation corpus, with and
without the current lists, and recorded with its date in
`docs/explanation/meting-overdetectie-07.md`: precision, recall, leaks and false
positives, per type. How the values `statushouders`, `bewoners`,
`woningcorporaties`, `juni` and `wereldvluchtelingendag` are typed today SHALL be
recorded as counts per type. The record SHALL contain no document text.

#### Scenario: The baseline is recorded with its date

- **WHEN** the baseline measurement is taken
- **THEN** `meting-overdetectie-07.md` holds precision, recall, leaks and false
  positives per type, with and without lists, and the date

#### Scenario: The five words are counted, not quoted from documents

- **WHEN** the record says how the five words are typed today
- **THEN** it gives a count per type for each word and no sentence or passage
  from any document

### Requirement: No measurement or diagnostic logs a value

Nothing that measures or diagnoses detection SHALL log, print or write a detected
value or the text around it. Output SHALL be counts, types and identifiers that
carry no personal data.

#### Scenario: A measurement run writes no value

- **WHEN** the evaluation or a diagnostic over stored runs completes
- **THEN** its output, logs and report contain counts per type and no detected
  value
