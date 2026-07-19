## ADDED Requirements

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
