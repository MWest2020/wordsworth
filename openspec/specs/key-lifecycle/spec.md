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

### Requirement: Keys are scoped per PII type

Data keys SHALL be scoped per `domain/type`, where `domain` identifies a
pseudonymisation domain (e.g. a department) and `type` the PII type. The default
domain SHALL be `_global`; existing key rows scoped by type alone SHALL be read
as `_global/<type>` without migration. The same value under two domains SHALL
yield two different pseudonyms. Rotation, escrow and recovery operate per scope.

#### Scenario: Domains do not share pseudonyms

- **WHEN** the same BSN is pseudonymised in domain `wi` and in domain `mo`
- **THEN** the two tokens differ

#### Scenario: Legacy scope keeps working

- **WHEN** a key row scoped `PERSON` exists from before this change
- **THEN** it is used for `_global/PERSON` and existing tokens still reveal

### Requirement: Data keys are durably persisted as envelope-wrapped blobs

Data keys SHALL be persisted durably as ciphertext wrapped by an OpenBao Transit
KEK that never leaves OpenBao; only the wrapped material SHALL be stored, never
clear key bytes, and never in logs. A key provider constructed fresh over the same
vault and Transit (e.g. after a process restart) SHALL resolve the same active key
per scope and SHALL resolve any prior version by its `key_id`, so pseudonymised
data stays revealable across restarts.

#### Scenario: A fresh provider resolves persisted keys after a restart

- **WHEN** data is pseudonymised, then a brand-new key provider is constructed over
  the same durable vault and Transit
- **THEN** the new provider resolves the same key material and the data
  deanonymises to its originals

### Requirement: Fail-closed on unwrap failure

If the Transit unwrap of a data key fails, the key provider SHALL raise and SHALL
NOT fall back to any clear or substitute key, so reveal and new-type
pseudonymisation degrade safely rather than leak.

#### Scenario: Unwrap failure raises

- **WHEN** the Transit backend cannot unwrap a stored key
- **THEN** resolving that key raises and no clear key material is produced

### Requirement: At most one active key per scope

The key vault SHALL hold at most one `active` key per scope, enforced by the
datastore (not only by code). When two writers concurrently mint a first key for
the same scope, exactly one SHALL become active and the other SHALL be rejected;
the rejected writer SHALL adopt the winning active key rather than create a second
active row. Retired versions remain resolvable by `key_id`.

#### Scenario: A concurrent second active is rejected and the winner adopted

- **WHEN** two providers concurrently mint a first active key for the same scope
- **THEN** the datastore rejects the second active insert, and the losing provider
  re-reads and returns the winning active key — never two active rows for the scope

### Requirement: Process-lifetime provider warms the unwrap cache

The durable key provider SHALL be usable as a single process-lifetime instance
backed by a session-factory vault store, so its in-memory unwrap cache persists
across requests. Repeated resolutions of the same key within the cache TTL SHALL
unwrap via the KEK at most once.

#### Scenario: Repeated resolutions unwrap once

- **WHEN** one long-lived provider resolves the same key several times within the
  cache TTL
- **THEN** the Transit unwrap is performed once and subsequent resolutions are
  served from the cache

### Requirement: Grants are domain-bound

A grant MAY name a domain. A grant without a domain SHALL authorise reveal in
`_global` only; it SHALL never match all domains implicitly.

#### Scenario: Grant without domain is fail-safe

- **WHEN** a grant without `domain` is used to reveal a document ingested in
  domain `wi`
- **THEN** every type is withheld

