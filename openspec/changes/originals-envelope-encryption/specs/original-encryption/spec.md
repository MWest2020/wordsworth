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

### Requirement: Key material never leaves the key path in clear

Clear data-key material SHALL NOT be written to disk, logged, or included in an
error message.

#### Scenario: A failure says nothing about the key

- **WHEN** sealing or opening fails
- **THEN** the logs and the error contain no data-key bytes in any encoding
