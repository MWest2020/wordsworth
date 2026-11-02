## ADDED Requirements

### Requirement: A failed ingest removes only the object it wrote

When ingest fails after it wrote the original, it SHALL delete that object. It
SHALL NOT delete an object it did not write.

#### Scenario: Failure after a write

- **WHEN** ingest fails after the original was written
- **THEN** the written object is deleted and no document or key row remains

#### Scenario: Failure after finding an existing object

- **WHEN** the bytes of a live document are ingested again and a later step
  fails
- **THEN** the existing object of the live document is still stored
