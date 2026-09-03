## ADDED Requirements

### Requirement: Column-selected pseudonymisation by profile

wordsworth SHALL pseudonymise tabular (CSV) data according to a profile naming
the domain, the columns to transform and their PII types, and the mode
(`per_attribute` or `per_record`). Columns not named SHALL pass through
unchanged. No PII detection SHALL be applied to the selected columns.

#### Scenario: Selected columns are replaced, others kept

- **WHEN** a CSV with columns `bsn,naam,uitkering` is processed with a profile
  selecting `bsn` and `naam`
- **THEN** `bsn` and `naam` hold pseudonyms and `uitkering` is byte-identical

### Requirement: Dataset and document pseudonyms coincide

In `per_attribute` mode a cell SHALL be pseudonymised with the same key scope,
normalisation and derivation as the same value in a document of the same
domain, so the tokens are equal.

#### Scenario: Cross-path consistency

- **WHEN** BSN `123456789` appears in an ingested document and in a dataset cell
  of type BSN in the same domain
- **THEN** both produce the same token

### Requirement: Per-record pseudonym

In `per_record` mode a row SHALL receive one pseudonym derived from the
`record_key` columns joined with `|` in profile order, empty cells as `""`,
under type `RECORD`; all non-empty selected cells of that row SHALL carry it
(an empty cell stays empty). Rows whose key cells are all empty SHALL be
counted and reported (`rows_without_record_key`).

#### Scenario: Same person, same record pseudonym

- **WHEN** two rows share the same normalised `record_key` values
- **THEN** they receive the same record pseudonym

### Requirement: Missed-column validation is advisory

When PII validation is requested, unselected columns SHALL be sampled through
the detectors and hits reported as warnings. The run SHALL never transform a
column the profile did not select.

#### Scenario: Warning, not action

- **WHEN** an unselected column contains values that pass the BSN elfproef
- **THEN** the response lists that column as a warning and the column is
  unchanged in the output

### Requirement: Runs are audited without values

Each run SHALL append one audit record with profile hash, domain, row count,
transformed columns, unique-pseudonym count and normalisation version, and no
cell values.

#### Scenario: Audit record shape

- **WHEN** a dataset run completes
- **THEN** exactly one audit record is appended and it contains no input value
