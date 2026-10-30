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

A deleted document SHALL NOT count as existing: every rule that asks whether a
document already exists SHALL treat state DELETED as not existing, because
deletion keeps the row and does not set `superseded_by`.

#### Scenario: Identical bytes ingested twice

- **WHEN** the same bytes are ingested a second time
- **THEN** one wrapped key exists and the original ciphertext is unchanged

#### Scenario: Bytes of a deleted document are ingested again

- **WHEN** bytes are ingested whose only document is in state DELETED
- **THEN** a new document is created with its own new data key, and the
  deleted document's ciphertext and key are not reused

### Requirement: Every original write is encrypted

Every write of an original, including OCR recovery, SHALL go through the
envelope path, and `object_key` SHALL point to the ciphertext. No plaintext
original SHALL be written.

#### Scenario: OCR recovery writes ciphertext

- **WHEN** an `unprocessable_ocr` document is recovered
- **THEN** the OCR'd PDF in the store is ciphertext and the document's
  `object_key` points to it

### Requirement: Ingest fails closed without the key service

Ingest SHALL fail with a named error when the key service is unreachable, and
SHALL NOT store the original in clear as a fallback.

#### Scenario: OpenBao is unreachable

- **WHEN** a document is ingested while OpenBao cannot be reached
- **THEN** ingest fails with the named error and nothing is written to the
  object store

#### Scenario: Irreversible mode needs the key service too

- **WHEN** a document is ingested in irreversible mode while OpenBao cannot be
  reached
- **THEN** ingest fails with a clear error and the original is not stored in
  clear

### Requirement: Keys are backed up before originals are sealed

`document_keys` SHALL be backed up and the KEK escrowed before this change is
deployed; the deploy task and the runbook SHALL say so.

#### Scenario: Deploy without backup

- **WHEN** the deploy task is followed
- **THEN** it requires the `document_keys` backup and the KEK escrow before
  any original is sealed

### Requirement: Key material never leaves the key path in clear

Clear data-key material SHALL NOT be written to disk, logged, or included in an
error message.

#### Scenario: A failure says nothing about the key

- **WHEN** sealing or opening fails
- **THEN** the logs and the error contain no data-key bytes in any encoding
