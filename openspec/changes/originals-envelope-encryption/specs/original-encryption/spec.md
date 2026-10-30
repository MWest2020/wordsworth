## ADDED Requirements

### Requirement: Originals are stored encrypted

Ingest SHALL store every new original document encrypted under its own random
data key with AES-256-GCM, bound by associated data to the document id and
the SHA-256 of the plaintext; the data key SHALL be persisted only wrapped by
the domain's key-encryption key.

#### Scenario: The stored object is ciphertext

- **WHEN** a PDF is ingested
- **THEN** the object in the store starts with the encryption header and does
  not contain the PDF's text

#### Scenario: A tampered or swapped object does not open

- **WHEN** a sealed object's bytes are changed, or it is read as another
  document's original
- **THEN** opening fails and no plaintext is returned

#### Scenario: No key, no plaintext

- **WHEN** the key-encryption key is unavailable or wrong
- **THEN** opening fails closed, without falling back to reading the object as
  plaintext

### Requirement: Re-ingest does not re-seal

Ingest SHALL assign the document id before writing to the store. When the
registry returns an existing document for identical bytes, ingest SHALL NOT
re-seal and SHALL NOT overwrite: it SHALL reuse the existing ciphertext and
wrapped key. Each data key SHALL belong to exactly one live document.

#### Scenario: Identical bytes ingested twice

- **WHEN** the same bytes are ingested a second time
- **THEN** one wrapped key exists and the original ciphertext is unchanged

### Requirement: Ingest fails closed without the key service

Ingest SHALL fail with a named error when the key service is unreachable, and
SHALL NOT store the original in clear as a fallback.

#### Scenario: OpenBao is unreachable

- **WHEN** a document is ingested while OpenBao cannot be reached
- **THEN** ingest fails with the named error and nothing is written to the
  object store

### Requirement: Key material never leaves the key path in clear

Clear data-key material SHALL NOT be written to disk, logged, or included in an
error message.

#### Scenario: A failure says nothing about the key

- **WHEN** sealing or opening fails
- **THEN** the logs and the error contain no data-key bytes in any encoding
