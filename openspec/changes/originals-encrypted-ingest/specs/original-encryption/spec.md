## ADDED Requirements

### Requirement: New originals are stored sealed

Ingest SHALL register the document before writing its original and SHALL write
the original sealed under the document's data key. Bytes already stored for a
live document SHALL NOT be written again.

#### Scenario: The stored object is ciphertext

- **WHEN** a PDF is ingested
- **THEN** the stored object starts with the sealed header, does not contain
  the PDF's text, and opens to the ingested bytes

#### Scenario: Identical bytes ingested twice

- **WHEN** the same bytes are ingested a second time
- **THEN** one document and one key row exist and the stored object is
  unchanged

#### Scenario: A failed ingest leaves nothing behind

- **WHEN** ingest fails after the key row was written, before or after the
  object write
- **THEN** after the rollback no document points at an object it cannot open,
  and an ingest of the same bytes afterwards yields a document whose original
  opens

### Requirement: Ingest fails closed without the key service

Ingest SHALL fail with a named error when the key service is unreachable or
refuses, in every pseudonymisation mode, and SHALL NOT store the original in
clear as a fallback.

#### Scenario: OpenBao is unreachable

- **WHEN** a document is ingested while OpenBao cannot be reached
- **THEN** the API answers 503 with `key service unavailable` and nothing is
  written to the object store

#### Scenario: Irreversible mode needs the key service too

- **WHEN** a document is ingested in irreversible mode while OpenBao cannot be
  reached
- **THEN** ingest fails the same way and the original is not stored in clear

### Requirement: A sealed original is never served damaged

A read of a sealed original that fails to open SHALL give an error and SHALL
NOT return the stored bytes.

#### Scenario: Tampered or swapped object at the PDF routes

- **WHEN** the redacted or reveal PDF is requested for a document whose sealed
  object was changed or swapped with another sealed object
- **THEN** the route answers with an error and no PDF bytes

### Requirement: Originals are not logged in clear

Ingest, processing and the PDF routes SHALL NOT write original content or
clear data-key material to the logs, including on failure.

#### Scenario: Logs during ingest and failure

- **WHEN** a document is ingested, processed and served, and the failure cases
  run, with log capture
- **THEN** no marker string from the PDF and no data-key bytes in any encoding
  appear in the captured logs

### Requirement: Keys are backed up before originals are sealed

The deployment that first seals originals SHALL be preceded by a tested
backup of `document_keys` and an off-node OpenBao snapshot containing the KEK;
the how-to SHALL state this precondition.

#### Scenario: Deploy precondition

- **WHEN** the how-to for encrypted originals is followed for a deploy
- **THEN** it requires the tested `document_keys` backup and the KEK snapshot
  before any original is sealed
