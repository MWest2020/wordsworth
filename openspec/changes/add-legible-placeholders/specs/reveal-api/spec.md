## ADDED Requirements

### Requirement: Legible placeholder view

`GET /documents/{id}/anonymized` SHALL accept `view=legible`, rendering each
distinct keyed token as a numbered, Dutch-labelled placeholder
(`[PERSOON 1]`, `[ADRES 2]`), numbered per type in order of first occurrence
within the document, with a `legend` mapping each placeholder back to its
token. The default view SHALL remain the stored token text. The stored text and
the index SHALL not change.

#### Scenario: Same token, same ordinal

- **WHEN** `[PERSON:3fa9c2d1]` occurs twice and `[PERSON:9b0e11aa]` once
- **THEN** the legible view shows `[PERSOON 1]` twice and `[PERSOON 2]` once,
  and the legend has exactly two PERSOON entries

#### Scenario: Default is unchanged

- **WHEN** the endpoint is called without `view`
- **THEN** the response equals today's token text
