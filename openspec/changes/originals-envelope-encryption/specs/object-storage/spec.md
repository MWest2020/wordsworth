## MODIFIED Requirements

### Requirement: Ingest stores, pipeline fetches by key

Ingest SHALL store the document bytes and record the object key; the pipeline
SHALL fetch the bytes by key rather than receiving them directly. For an
original document the stored bytes SHALL be its encrypted form (ADR-0008), and
the pipeline SHALL receive the decrypted bytes through the encrypting store.

#### Scenario: Pipeline reads from the object store

- **WHEN** a document is processed
- **THEN** its bytes are fetched from the object store by its recorded key

#### Scenario: The pipeline sees plaintext, the store holds ciphertext

- **WHEN** an encrypted original is processed
- **THEN** the pipeline receives the original bytes, while the object store
  holds only the ciphertext
