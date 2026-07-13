## ADDED Requirements

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
audit stream** — NOT to the document hash-chain. The document audit trail is the
document state machine (its records carry a mandatory `document_id`), and a
system-wide key rotation has no document; it SHALL NOT be forced into that chain
via a synthetic document or a nullable `document_id`. The rotation event SHALL
record the old and new `key_id` and the actor, and SHALL NOT log any key
material.

#### Scenario: Rotation records old and new key id without key material

- **WHEN** the key provider is rotated
- **THEN** the key-lifecycle audit stream gains an event naming the old and new
  `key_id` and the actor, no key material is present, and the document
  hash-chain is unchanged
