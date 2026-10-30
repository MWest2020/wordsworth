## ADDED Requirements

### Requirement: Existing originals are sealed without losing one

The seal run SHALL replace a legacy plaintext original only after its sealed
form has been verified to decrypt to bytes with the recorded SHA-256, and
SHALL report counts before and after.

#### Scenario: A failed seal keeps the original

- **WHEN** the sealed copy of an original does not verify
- **THEN** the plaintext original stays in place and the document is reported
  as failed

#### Scenario: A dry run changes nothing

- **WHEN** the seal run is started with `--dry-run`
- **THEN** the store and the database are unchanged and the report lists what
  would be sealed
