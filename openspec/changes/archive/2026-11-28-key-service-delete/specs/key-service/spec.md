## ADDED Requirements

### Requirement: Deleting a document removes its keys, tokens, orphaned values and scoped grants

Deleting a document in the key service SHALL destroy its data keys, remove its
registry rows, every encrypted value no other document is registered for and
every grant scoped to that document, and keep only a tombstone with the
document's id and domain. A value another
document still holds SHALL survive, also when that other document is being
pseudonymised at the same moment.

#### Scenario: A shared value survives

- **WHEN** a document is deleted while another document holds the same token
- **THEN** that token's encrypted value remains and the other document's
  registry row is untouched

#### Scenario: Deleted means unopenable

- **WHEN** a document's keys have been destroyed
- **THEN** no sealed object of the document can be decrypted by the service

#### Scenario: Grants scoped to the document go with it

- **WHEN** a document with a grant scoped to it and an unscoped grant is
  deleted
- **THEN** the scoped grant is gone, the unscoped one remains, and the answer
  reports one grant deleted

### Requirement: Locks are taken in one order, key lifecycle before audit

Every writer of the key service's database SHALL take its locks in one
documented order, in which the key-lifecycle chain is taken before the audit
chain and the audit chain is the last lock of any transaction.

#### Scenario: Two deletes and a seal do not deadlock

- **WHEN** a document deletion, an originals deletion and a seal run against
  each other
- **THEN** all complete and none is aborted by a deadlock
