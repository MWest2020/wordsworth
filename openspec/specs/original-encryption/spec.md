# original-encryption Specification

## Purpose
Created by the change `originals-cipher-and-key-store`. ADR-0008 (accepted 2026-10-30) seals every original PDF under its own data key.

## Requirements

### Requirement: A sealed original opens only under its own object key

A sealed original SHALL carry a versioned header and be encrypted with
AES-256-GCM under its own data key, with associated data binding it to the
object key it was sealed for and the key id in its header. Opening it under any
other object key, or after any byte of it changed, SHALL fail and SHALL return
no plaintext.

#### Scenario: Round trip

- **WHEN** an original is sealed for a document and object key and opened again
- **THEN** the opened bytes equal the original bytes

#### Scenario: Tampering and swapping fail closed

- **WHEN** a ciphertext or tag byte is flipped, the header key id is changed,
  or the sealed bytes are copied to another object key or swapped with another
  sealed object
- **THEN** opening raises an error and no plaintext is returned

### Requirement: Data keys are stored only wrapped

Each sealed object's data key SHALL be stored only wrapped by the KEK of the
document's domain, one `document_keys` row per object, recording which KEK
wrapped it. A tampered wrapped key, a different KEK or an unreachable key
service SHALL make the key unavailable, with a named error and no key material.

#### Scenario: Wrapped at rest

- **WHEN** a data key is minted for an object
- **THEN** its row holds only the wrapped key and the KEK reference, never the
  clear key

#### Scenario: Unavailable key fails closed

- **WHEN** the wrapped key was tampered with, another KEK is used, or the key
  service raises
- **THEN** unwrapping raises `OriginalsKeyUnavailable` and returns no key

### Requirement: Writing an original never overwrites readable bytes

Writing an original SHALL use the object's existing data key when the object
has a key row, SHALL NOT write when the stored object already opens under that
row, and SHALL NOT overwrite a legacy plaintext object. A failure between the
key row and the object write SHALL leave no document pointing at bytes it
cannot open, and no plaintext.

#### Scenario: Re-ingest does not re-seal

- **WHEN** the same bytes are written again for an object that opens under its
  key row
- **THEN** nothing is written, the call returns `PutResult.UNCHANGED` and the
  object still opens

#### Scenario: A legacy object survives a failed commit

- **WHEN** a write returns `PutResult.LEGACY` and the caller's commit then
  fails
- **THEN** the caller does not delete the object and it still reads

#### Scenario: A written object is removed after a failed commit

- **WHEN** a write returns `PutResult.WROTE` and the caller's commit then fails
- **THEN** the caller deletes the object it wrote

#### Scenario: The result has no truthiness

- **WHEN** a `PutResult` is used as a boolean
- **THEN** `TypeError` is raised

#### Scenario: A rolled-back write is repaired, not compounded

- **WHEN** a write fails after the object was written and before the commit,
  and the same bytes are written again later
- **THEN** the second write leaves one key row and an object that opens

#### Scenario: Legacy objects are left alone

- **WHEN** an original is written for an object that is stored as legacy
  plaintext, with no key row or with a key row that does not yet record the
  object as sealed
- **THEN** the object is not overwritten and the call returns
  `PutResult.LEGACY`

#### Scenario: A downgraded object is not overwritten

- **WHEN** an original is written for an object without a sealed header whose
  key row records it as sealed
- **THEN** the write raises and nothing is written

### Requirement: The unwrap cache is bounded in size and time

Unwrapped data keys SHALL be cached in a cache with a fixed maximum size whose
entries expire after the configured key cache TTL.

#### Scenario: Size bound

- **WHEN** more objects are opened than the cache size
- **THEN** the cache holds at most its size and an evicted key is unwrapped
  again through the key service

#### Scenario: Time bound

- **WHEN** an entry is older than the key cache TTL
- **THEN** the key is unwrapped again through the key service

### Requirement: Ciphertext is never handed out as a document

The plain object read SHALL refuse a sealed object, and the original read SHALL
refuse an object without a sealed header whose key row records it as sealed.

#### Scenario: Plain read of a sealed object

- **WHEN** a sealed object is read through the plain object store read
- **THEN** `SealedObjectError` is raised and no bytes are returned

#### Scenario: Downgrade

- **WHEN** an object whose key row records it as sealed is replaced by bytes
  without the header
- **THEN** reading it as an original raises

### Requirement: Clear key material never reaches logs

Clear data-key material SHALL NOT appear in any log line or exception message.

#### Scenario: Logs during failures

- **WHEN** sealing, opening and each failure case run with log capture
- **THEN** the data key is absent from the captured output in raw, hex and
  base64 form

### Requirement: Sealed objects that open under no key row are swept

A sealed object under `documents/` that opens under no key row (there is no row for its key, or
the row names another key id) and is older than one hour SHALL be listed by
`wordsworth-sealed-orphans` and removed only with `--apply`.

#### Scenario: Sweep

- **WHEN** the sweep runs with `--apply`
- **THEN** sealed orphans older than one hour are removed, and sealed objects
  that open under their row, young orphans and legacy objects are untouched

### Requirement: Originals are read and written through one seam

Code SHALL read an original only through `read_original` and write one only
through `write_original`. Given an originals store, these SHALL open and seal;
given a plain object store, they SHALL use the plain read and write, and the
plain read SHALL keep refusing a sealed object. The originals store SHALL be
usable wherever a plain object store is expected, for objects that are not
originals.

#### Scenario: A sealed original through the seam

- **WHEN** an original is written with `write_original` to an originals store
  and read back with `read_original`
- **THEN** the stored object is sealed and the read returns the original bytes

#### Scenario: A sealed object through a plain store

- **WHEN** `read_original` is given a plain object store holding a sealed object
- **THEN** `SealedObjectError` is raised and no bytes are returned

### Requirement: One Transit client per KEK name

The service SHALL build at most one Transit client per KEK name and share it
across its users.

#### Scenario: The same KEK name twice

- **WHEN** the transit factory is asked twice for the same KEK name
- **THEN** it returns the same client

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

### Requirement: The running service seals every new original

The API and every ingesting CLI SHALL write and read originals through one
originals store, in every pseudonymisation mode.

#### Scenario: The API's store

- **WHEN** the API starts with an object store configured
- **THEN** its store is an originals store, in reversible and in irreversible
  mode

#### Scenario: A CLI ingest

- **WHEN** a document is ingested with the corpus or manifest CLI
- **THEN** its original is stored sealed

### Requirement: A cached key is used only while its key row exists

Before using an unwrapped data key from its cache, the key store SHALL confirm
that the key row for that object still exists and names the same key. When it
does not, the cached key SHALL be dropped and SHALL NOT be used. The check
SHALL NOT call the key service. Every unwrap, with or without a cached key,
SHALL read the key row from the database as committed at that moment, never
from a copy the caller already holds in memory.

#### Scenario: The row was destroyed by another process

- **WHEN** a process holds an unwrapped key in its cache and another process
  destroys that key's row
- **THEN** the first process's next unwrap for that object raises
  `OriginalsKeyUnavailable` and returns no key

#### Scenario: The row was loaded earlier in the same session

- **WHEN** a session has loaded a key row, another process destroys that row,
  and the first session then unwraps that object with nothing in the cache
- **THEN** the unwrap raises `OriginalsKeyUnavailable` and the key service is
  not called

#### Scenario: The key was destroyed and minted again

- **WHEN** a key is destroyed and a new key is minted for the same object key
  while a process still caches the old one
- **THEN** that process's next unwrap returns the new key

#### Scenario: A cached key that still has its row

- **WHEN** a key is unwrapped twice within the cache TTL and its row is
  unchanged
- **THEN** the key service is called once

### Requirement: Existing originals are sealed without losing one

The seal run SHALL replace a legacy plaintext original only after its sealed
form has been verified to decrypt to bytes with the recorded SHA-256, and
SHALL report counts before and after.

#### Scenario: A failed seal keeps the original

- **WHEN** the sealed copy of an original does not verify
- **THEN** the plaintext original stays in place and the document is reported
  as failed

#### Scenario: A dry run changes nothing

- **WHEN** the seal run is started with `--dry-run`
- **THEN** the store and the database are unchanged and the report lists what
  would be sealed

#### Scenario: A rerun does not download what is sealed and committed

- **WHEN** the seal run meets an object whose key row has `sealed_at` set and
  whose first bytes are the sealed header
- **THEN** it reports the object `already_sealed` after reading the header
  only, never the whole object

### Requirement: The original scan of a live recovered document is sealed too

The seal run SHALL also seal the original scan of a document that is not
deleted and was recovered by OCR: the object named as `old_object_key` in its
recovering `ocr` audit record, when that object is still a legacy plaintext
original. A scan is also the object of a document that OCR recovery retired
as a copy of another document's object (a `supersede` record carrying
`as_object`) and that is not deleted. The same verify-before-replace rule and
the same report apply; the scan is counted separately (`scans`).

#### Scenario: A live recovered document's plaintext scan is sealed

- **WHEN** a document that is not deleted was recovered by OCR and its scan is
  still stored in plaintext
- **THEN** the seal run seals the scan, verifies it, replaces the plaintext and
  counts it under `scans`

#### Scenario: A scan that is already sealed or gone is left alone

- **WHEN** the scan of a live recovered document is already sealed, or no
  longer in the store
- **THEN** the seal run does nothing for it and reports nothing as failed

#### Scenario: A scan retired as a copy is sealed too

- **WHEN** OCR recovery retired a scan's document as a copy of another
  document's object (a `supersede` record carrying `as_object`), that
  document is not deleted, and its own object -- the scan -- is still stored
  in plaintext
- **THEN** the seal run seals that object under the same rules as any other
  scan (counted under `scans`, `gone` when the store no longer has it), and
  `--verify` fails while it is still plaintext

#### Scenario: A scan that is no longer in the store is skipped as gone

- **WHEN** the scan of a live recovered document is named in its `ocr` record
  but the store no longer has the object (it does not exist, or reading it
  raises an object-store error)
- **THEN** the seal run reports it with the status `gone`, counts it as neither
  sealed nor failed, and the run's exit status does not signal a failure
