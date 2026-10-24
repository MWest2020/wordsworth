## ADDED Requirements

### Requirement: A pilot report is made from a template with Mark's gate slots empty

The published-dossier pilot SHALL have a report template with sections for the
check, the corpus, the ranking gate, the PII gate and the findings. The check
section SHALL carry `checked_by`, `checked_at`, `robots_txt`, `anubis` and
`decision` from the pilot's `check.json`. The corpus section SHALL carry the
number of documents, the number of pages, the number of pages without a text
layer and the number of scans, and SHALL state that with no scans the OCR path
is barely tested. The ranking-gate and PII-gate sections SHALL be empty slots
that only Mark fills. A report made from the template SHALL leave a slot empty
until Mark fills it, and SHALL report a gate with an empty slot as not yet run,
not as passed.

#### Scenario: The template ships with empty gate slots

- **WHEN** the template is read
- **THEN** the ranking-gate and PII-gate sections contain no question, no
  timestamp and no identifier

#### Scenario: A gate whose slot is empty

- **WHEN** a report is written and Mark has not yet filled the ranking-gate or
  PII-gate slot
- **THEN** that gate is reported as not yet run, not as passed or failed

### Requirement: The ranking-gate slot proves the questions came first

The ranking-gate slot SHALL hold 5 questions each with the document Mark
expects, the time the questions were committed, the time of the first search
and the outcome. The gate SHALL pass when the expected document is in the top 8
for at least 4 of 5 questions, and SHALL be stated as gating this pilot run
only.

#### Scenario: Questions and timestamps are recorded

- **WHEN** Mark fills the ranking-gate slot
- **THEN** it holds 5 questions with expected documents, the commit time of the
  questions and the time of the first search

#### Scenario: Four of five in the top 8

- **WHEN** the expected document is in the top 8 for 4 of the 5 questions
- **THEN** the ranking gate passes for this pilot run

### Requirement: The PII-gate slot records Mark's read, not a recall figure

The PII-gate slot SHALL hold Mark's read of the anonymized text of the pilot
documents and any leftover direct identifier of a private person (name,
address, e-mail, phone, BSN, IBAN). The template and a report made from it
SHALL NOT use the word "recall" for PII, because published material is already
redacted by the municipality and there is no unredacted original to measure
misses against. The report SHALL state that anonymization of unpublished
documents remains unproven by this pilot.

#### Scenario: The word is absent

- **WHEN** the template is searched for the word "recall", case-insensitively
- **THEN** there is no match

#### Scenario: A leftover identifier

- **WHEN** Mark records a leftover direct identifier of a private person in a
  pilot document
- **THEN** the PII gate is reported as failed for that document unless it is
  excluded with the reason written down

### Requirement: The pilot report states the findings so far

The report SHALL state, as findings and not as fixes, that the 567-document
dossier `gooise-meren-woo-2022` has unknown provenance, and that provenance is
not recorded when a document is delivered again (a duplicate keeps its first
provenance and fails the manifest run).

#### Scenario: Findings are present

- **WHEN** a report is made from the template
- **THEN** it names both findings
