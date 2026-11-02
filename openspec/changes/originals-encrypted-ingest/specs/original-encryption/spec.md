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

#### Scenario: A batch stops at the first unavailable key

- **WHEN** a batch is ingested and the key service becomes unavailable at the
  second file
- **THEN** the first file stays stored, sealed, and the API answers 503 with
  `key service unavailable` and a per-file report of the first file; the
  second file and every file after it are not stored

#### Scenario: Irreversible mode needs the key service too

- **WHEN** a document is ingested in irreversible mode while OpenBao cannot be
  reached
- **THEN** ingest fails the same way and the original is not stored in clear
