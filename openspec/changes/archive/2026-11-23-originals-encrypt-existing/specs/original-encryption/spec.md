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

### Requirement: The original scan of a live recovered document is sealed too

The seal run SHALL also seal the original scan of a document that is not
deleted and was recovered by OCR: the object named as `old_object_key` in its
recovering `ocr` audit record, when that object is still a legacy plaintext
original. The same verify-before-replace rule and the same report apply; the
scan is counted separately (`scans`).

#### Scenario: A live recovered document's plaintext scan is sealed

- **WHEN** a document that is not deleted was recovered by OCR and its scan is
  still stored in plaintext
- **THEN** the seal run seals the scan, verifies it, replaces the plaintext and
  counts it under `scans`

#### Scenario: A scan that is already sealed or gone is left alone

- **WHEN** the scan of a live recovered document is already sealed, or no
  longer in the store
- **THEN** the seal run does nothing for it and reports nothing as failed

#### Scenario: A scan that is no longer in the store is skipped as gone

- **WHEN** the scan of a live recovered document is named in its `ocr` record
  but the store no longer has the object (it does not exist, or reading it
  raises an object-store error)
- **THEN** the seal run reports it with the status `gone`, counts it as neither
  sealed nor failed, and the run's exit status does not signal a failure

