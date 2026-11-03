## ADDED Requirements

### Requirement: New originals are stored sealed

Given an originals store, ingest SHALL register the document before writing its
original, and SHALL write the original sealed under the document's data key.
Bytes already stored for a live document SHALL NOT be written again.

#### Scenario: The stored object is ciphertext

- **WHEN** a PDF is ingested into an originals store
- **THEN** the stored object starts with the sealed header, does not contain
  the PDF's text, and opens to the ingested bytes

#### Scenario: Identical bytes ingested twice

- **WHEN** the same bytes are ingested a second time
- **THEN** one document and one key row exist and the stored object is
  unchanged

### Requirement: A failed ingest removes only the object it wrote

When ingest fails after it wrote the original, it SHALL delete that object. It
SHALL NOT delete an object it did not write.

#### Scenario: Failure after a write

- **WHEN** ingest fails after the original was written
- **THEN** the written object is deleted and no document remains

#### Scenario: Failure after finding an existing object

- **WHEN** the bytes of a live document are ingested again and a later step
  fails
- **THEN** the existing object of the live document is still stored and opens

### Requirement: Ingest fails closed without the key service

Ingest SHALL fail with a named error when the key service is unreachable or
refuses, in every pseudonymisation mode, and SHALL NOT store the original in
clear as a fallback. A batch SHALL stop at the first such failure and report
what it already stored.

#### Scenario: OpenBao is unreachable

- **WHEN** a document is ingested while the key service refuses
- **THEN** the API answers 503 with `detail` `key service unavailable` and
  nothing is written to the object store

#### Scenario: A batch stops at the first unavailable key

- **WHEN** a batch of three is ingested and the key service refuses from the
  second file on
- **THEN** the first file stays stored, sealed; the API answers 503 with
  `detail` `key service unavailable` and `results` listing the first file only;
  the second and third files are not stored

#### Scenario: Irreversible mode needs the key service too

- **WHEN** a document is ingested in irreversible mode while the key service
  refuses
- **THEN** ingest fails the same way and the original is not stored in clear
