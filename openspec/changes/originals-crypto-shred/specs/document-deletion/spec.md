## MODIFIED Requirements

### Requirement: Deleting a document removes its content

Deleting a document SHALL remove its stored object, its stored text, its
pseudonyms, its mappings, its index entries and its grants. The `documents` row
and the document's earlier audit records SHALL remain. For an encrypted
original, deleting SHALL also destroy its data key unless another live document
still uses that key.

#### Scenario: Nothing of the content is left

- **WHEN** an indexed document is deleted
- **THEN** its object, text, pseudonyms, mappings, index entries and grants are
  gone, and a search no longer returns it

#### Scenario: The trail is kept

- **WHEN** a document is deleted
- **THEN** its earlier audit records and the hash chain are unchanged and still
  verify

#### Scenario: A surviving copy is unreadable

- **WHEN** an encrypted document is deleted and a copy of its object made
  before the deletion still exists
- **THEN** that copy can no longer be decrypted

#### Scenario: A shared key outlives one of its documents

- **WHEN** one of two documents sharing a de-duplicated original is deleted
- **THEN** the data key remains, and the other document's original still opens
