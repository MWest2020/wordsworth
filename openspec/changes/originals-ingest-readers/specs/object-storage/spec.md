## MODIFIED Requirements

### Requirement: Ingest stores, pipeline fetches by key

Ingest SHALL store the document bytes and record the object key; the pipeline
SHALL fetch the bytes by key rather than receiving them directly. Every read
of an original document SHALL go through the originals seam, which opens a
sealed original and refuses a sealed object through a plain store.

#### Scenario: Pipeline reads from the object store

- **WHEN** a document is processed
- **THEN** its bytes are fetched from the object store by its recorded key

#### Scenario: Every reader opens a sealed original

- **WHEN** a sealed document is processed, reanonymized, OCR-recovered, or its
  redacted or reveal PDF is requested
- **THEN** its original is opened through the originals seam and the plaintext
  bytes are used
