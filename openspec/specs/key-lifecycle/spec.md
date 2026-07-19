# key-lifecycle Specification

## Purpose
TBD - created by archiving change add-key-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Versioned keys with rotation

The `KeyProvider` SHALL support multiple key versions identified by `key_id`, a
current (active) key, resolution of any version by id, and a `rotate` operation
that makes a new key active without destroying prior versions.

#### Scenario: Rotation adds a new active key

- **WHEN** the key provider is rotated
- **THEN** a new active key is returned and prior key versions remain resolvable
  by their `key_id`

### Requirement: Deanonymization selects the key by stored key_id

Deanonymization SHALL decrypt each mapping with the key identified by that
mapping's stored `key_id`, so entries under any key version decrypt correctly.

#### Scenario: Mixed-key mappings all decrypt

- **WHEN** some mappings were encrypted before rotation and some after
- **THEN** all decrypt using their respective stored key ids

### Requirement: Mapping re-encryption without touching documents

Rotation SHALL be completable by re-encrypting mapping entries from the old key to
the new (updating `key_id`); documents and the index SHALL NOT be modified.

#### Scenario: Re-encrypt leaves documents untouched

- **WHEN** mappings are re-encrypted to a new key
- **THEN** each entry now decrypts under the new key and no document is changed

### Requirement: Open escrow and recovery

Keys SHALL be stored and escrowed via open, non-commercial tooling (SOPS+age or
OpenBao); CyberArk/Conjur SHALL NOT be used. Recovery SHALL restore usable key
material from escrow.

#### Scenario: Recovered key decrypts its mappings

- **WHEN** a key is recovered from escrow
- **THEN** mappings encrypted under that key id decrypt successfully

### Requirement: Rotation is audited in a separate key-lifecycle stream

Rotation SHALL emit an audit event to a **separate, append-only key-lifecycle
audit stream** — NOT to the document hash-chain. Rotation SHALL NOT create or
reuse a synthetic/sentinel document, and the audit table's `document_id` SHALL
remain a NOT-NULL foreign key carrying only real documents. The rotation event SHALL record
the old and new `key_id`, the number of mappings re-encrypted, and the actor, and
SHALL NOT log any key material.

#### Scenario: Rotation does not touch the document chain

- **WHEN** the key provider is rotated
- **THEN** the key-lifecycle audit stream gains an event naming the old and new
  `key_id` and the actor, no key material is present, and the document hash-chain
  gains no record

#### Scenario: No synthetic document exists

- **WHEN** rotations have occurred
- **THEN** the documents table contains no sentinel/system document and querying
  any real document's history returns only its own audit records

