## MODIFIED Requirements

### Requirement: Rotation is audited in a separate key-lifecycle stream

Rotation, and every other change to an authorisation fact that has no document
of its own — a grant issued or revoked, a role changed, a dossier renamed —
SHALL emit an event to a **separate key-lifecycle audit stream**, NOT to the
document hash-chain. No event SHALL create or reuse a synthetic or sentinel
document, and the audit table's `document_id` SHALL remain a NOT-NULL foreign
key carrying only real documents. A rotation event SHALL record the old and new
`key_id`, the number of mappings re-encrypted, and the actor, and no event SHALL
log key material.

The stream SHALL be stored in PostgreSQL, SHALL survive a restart of any
process that writes to it, SHALL be append-only at the schema level (an UPDATE
or DELETE raises), and SHALL be hash-chained so that altering one event is
detectable at that event.

#### Scenario: Rotation does not touch the document chain

- **WHEN** the key provider is rotated
- **THEN** the key-lifecycle audit stream gains an event naming the old and new
  `key_id` and the actor, no key material is present, and the document
  hash-chain gains no record

#### Scenario: No synthetic document exists

- **WHEN** rotations and other lifecycle events have occurred
- **THEN** the documents table contains no sentinel or system document, and
  querying any real document's history returns only its own audit records

#### Scenario: An event survives a restart

- **WHEN** a grant is revoked and the process that recorded it then restarts
- **THEN** the `grant_revoked` event is still in the stream

#### Scenario: An event cannot be changed

- **WHEN** an UPDATE or DELETE is issued against a stream row
- **THEN** it is refused by the database

#### Scenario: Tampering is detectable

- **WHEN** a stream row's content is altered outside the application
- **THEN** verifying the chain reports the first bad `seq`

## ADDED Requirements

### Requirement: Every path that changes an authorisation fact reaches the stream

Each production entry point that issues or revokes a grant, changes a role,
renames a dossier or rotates a key SHALL record the event in the key-lifecycle
stream. A production writer that has no stream to write to SHALL fail rather
than return silently.

A missing record must be an error someone sees, not a default someone chose.
The rename path went unrecorded behind exactly such a default.

#### Scenario: A rename through the command line is recorded

- **WHEN** a dossier is renamed with `wordsworth-dossier-hernoem`
- **THEN** the stream holds a `dossier_renamed` event with the old name, the new
  name, the number of documents it held, and the actor

#### Scenario: No stream is a failure, not a no-op

- **WHEN** a production writer is invoked without a stream
- **THEN** it raises, and nothing about the change is reported as done
