## ADDED Requirements

### Requirement: Sub-threshold detector noise is not PII

Reversible entity pseudonymisation SHALL ignore detected entity values shorter
than a minimum length (model/OCR noise), neither redacting them nor letting them
trip the survivor fail-hard check. Real structured PII is covered by the
deterministic detectors, and genuine entity PII meets the minimum length.

#### Scenario: A 2-char noise span does not reject the document

- **WHEN** the detector reports a 1-2 char span that recurs in ordinary text
- **THEN** it is left untouched, the document is still pseudonymised for its real
  entities, and no fail-hard is raised
