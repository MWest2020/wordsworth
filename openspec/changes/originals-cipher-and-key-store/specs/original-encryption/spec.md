## ADDED Requirements

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
- **THEN** nothing is written and the object still opens

#### Scenario: A rolled-back write is repaired, not compounded

- **WHEN** a write fails after the object was written and before the commit,
  and the same bytes are written again later
- **THEN** the second write leaves one key row and an object that opens

#### Scenario: Legacy objects are left alone

- **WHEN** an original is written for an object that is stored as legacy
  plaintext
- **THEN** the object is not overwritten and the call reports it as legacy

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
