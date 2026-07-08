## ADDED Requirements

### Requirement: Key provider protocol

Encryption keys SHALL be obtained through a `KeyProvider` protocol so the key
source is swappable. The PoC ships a stub provider deriving a single key from a
user-supplied passphrase; production key lifecycle (rotation, escrow, recovery)
is out of scope for the PoC.

#### Scenario: Stub key is deterministic for a passphrase

- **WHEN** the stub provider is asked for the current key twice with the same
  passphrase
- **THEN** it returns the same key bytes and key id

### Requirement: Separated encrypted mapping store

Pseudonym-to-original mappings SHALL be held in a separated store as AES-GCM
ciphertext, never in the document and never as clear PII. The store SHALL be
reached through a `MappingStore` protocol, and storing a pseudonym SHALL be
idempotent.

#### Scenario: Mapping is stored as ciphertext

- **WHEN** a pseudonym and its original value are stored
- **THEN** only ciphertext (with nonce and key id) is persisted, not the original

#### Scenario: Storing the same pseudonym twice is idempotent

- **WHEN** the same pseudonym is stored a second time
- **THEN** the store keeps a single mapping for that pseudonym

### Requirement: Stable keyed pseudonyms

The `Pseudonymizer` SHALL reuse the deterministic detectors and replace each PII
value with a stable, keyed pseudonym, such that the same value yields the same
pseudonym (searchable/linkable) while the pseudonym is not reversible without the
mapping store. The search index SHALL see only pseudonyms, never clear PII.

#### Scenario: Same value yields the same pseudonym

- **WHEN** a value appears more than once (in one or more documents)
- **THEN** every occurrence is replaced by the identical pseudonym

#### Scenario: A pseudonymized document is reversible via the store

- **WHEN** deanonymization is applied with the key and mapping store
- **THEN** the original values are recovered from the store

### Requirement: Pseudonymizer is a de-identify driver

The `Pseudonymizer` SHALL satisfy the `Anonymizer` protocol so it can be injected
into the pipeline's de-identify step without pipeline changes. The pipeline
default SHALL remain irreversible anonymization.

#### Scenario: Injected pseudonymizer produces pseudonymized index text

- **WHEN** the pipeline runs with the pseudonymizer injected
- **THEN** the persisted (index-bound) text contains pseudonyms and the mapping
  store holds the reversible encrypted originals

### Requirement: Deanonymization is audit-logged

Every deanonymization SHALL append a record to the append-only, hash-chained
audit trail, recording the pseudonyms and the actor. It SHALL NOT log the
recovered clear values.

#### Scenario: Deanonymization writes a chained audit record

- **WHEN** a document's text is deanonymized
- **THEN** a `deanonymize` audit record is appended for that document, the chain
  still verifies, and the payload holds pseudonyms and actor but no clear values
