## MODIFIED Requirements

### Requirement: Ingest stores, pipeline fetches by key

Ingest SHALL store the document bytes and record the object key; the pipeline
SHALL fetch the bytes by key rather than receiving them directly. Every write
and every read of an original document SHALL go through the originals store,
which seals on write and opens on read; no reader SHALL fetch an original with
the plain object read.

#### Scenario: Pipeline reads from the object store

- **WHEN** a document is processed
- **THEN** its bytes are fetched from the object store by its recorded key

#### Scenario: Every reader opens through the originals store

- **WHEN** a sealed document is processed, reanonymized, OCR-recovered, or its
  redacted or reveal PDF is requested
- **THEN** its original is read through the originals store and the plaintext
  bytes are used
