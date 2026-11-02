## ADDED Requirements

### Requirement: Ingest registers the document before it writes the original

Ingest SHALL register the document, so that its id exists, before it writes the
sealed original, because the key row carries the document id.

#### Scenario: Key row carries the registered document id

- **WHEN** a PDF is ingested
- **THEN** the document row exists before the original is written and the key
  row's document id is that document's id

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

### Requirement: A failed batch reports what was committed

When a batch to `POST /ingest` stops on an unavailable key, the 503 body SHALL
list the files already committed in that request.

#### Scenario: Body lists the committed files

- **WHEN** a three-file batch fails on the second file because the key service
  is unavailable
- **THEN** the 503 body lists the first file and neither the second nor the
  third

### Requirement: OCR recovery reads its input through the originals store

OCR recovery SHALL read the original it recovers through the originals store.
Until `originals-ocr-sealed`, it still writes the recovered PDF as a plain
object; that gap is stated, not hidden.

#### Scenario: Recovery of a sealed scan

- **WHEN** OCR recovery runs on a document whose original is sealed
- **THEN** the original is read through the originals store and recovery
  processes its plaintext bytes
