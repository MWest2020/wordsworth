## MODIFIED Requirements

### Requirement: Deleting a document removes its content

Deleting a document SHALL remove its stored object, its stored text, its
pseudonyms, its mappings, its index entries and its grants. The `documents` row
and the document's earlier audit records SHALL remain. For an encrypted
original, deleting SHALL also destroy the data key of every object whose last
claim the deletion ends, in the same transaction.

#### Scenario: Nothing of the content is left

- **WHEN** an indexed document is deleted
- **THEN** its object, text, pseudonyms, mappings, index entries and grants are
  gone, and a search no longer returns it

#### Scenario: The trail is kept

- **WHEN** a document is deleted
- **THEN** its earlier audit records and the hash chain are unchanged and still
  verify

#### Scenario: A surviving copy is unreadable

- **WHEN** an encrypted document is deleted, a copy of its object made before
  the deletion still exists, and no other document that is not deleted points
  at its object
- **THEN** that copy can no longer be decrypted, and the document's key is gone

#### Scenario: Another replica cannot open it after the delete

- **WHEN** one replica deletes an encrypted document whose object no other
  document that is not deleted points at, while another replica still holds
  its unwrapped key in memory
- **THEN** the other replica can no longer open a copy of that object, without
  waiting for its cache to expire

## ADDED Requirements

### Requirement: A data key is destroyed with the last claim on its object

A deletion SHALL destroy a data key exactly when it ends the last claim on that
key's object: when no other document that is not deleted still points at the
same object key. A document with more than one sealed object SHALL lose the key
of each. Every caller of a deletion SHALL destroy keys in the same way, whether
or not it has a key service. The `deleted` record and the dry run SHALL carry
the number of keys destroyed, a dossier deletion SHALL report their sum, and
none of them SHALL carry key material. A failure to destroy a key SHALL be a
hard error as any other failed removal: no `deleted` record, the document in
its previous state. An original that was never encrypted has no key, and its
deletion SHALL behave as before.

#### Scenario: Deleting a superseded copy leaves the survivor's key

- **WHEN** a superseded copy is deleted whose object key is also the object key
  of its survivor
- **THEN** the key still exists and the survivor's original can still be opened

#### Scenario: The key goes with the last claim

- **WHEN** a document is deleted while a superseded copy that is not deleted
  still points at its object, and that copy is deleted afterwards
- **THEN** the object and its key are kept after the first deletion and are
  both gone after the second

#### Scenario: A copy and its survivor are deleted at the same moment

- **WHEN** two deletions run at once, one for a superseded copy and one for its
  survivor on the same object key
- **THEN** after both have finished the object and its key are gone

#### Scenario: A scan and its OCR'd PDF

- **WHEN** a document recovered by OCR is deleted
- **THEN** the key of the scan and the key of the OCR'd PDF are both gone and
  the record counts two keys

#### Scenario: The command-line deletion has no key service

- **WHEN** `wordsworth-delete` deletes an encrypted document without a key
  service configured
- **THEN** the document's key is gone, as after a deletion through the API

#### Scenario: The key cannot be destroyed

- **WHEN** destroying the key fails during a deletion
- **THEN** the call fails, no `deleted` record exists, the document is in its
  previous state, and a later call completes the deletion

#### Scenario: The dry run counts keys

- **WHEN** the CLI runs with `--dry-run` on an encrypted document
- **THEN** it reports the number of keys that would be destroyed, and every key
  still exists

#### Scenario: A dossier reports the sum

- **WHEN** a dossier is deleted, or its deletion is run with `--dry-run`
- **THEN** the report carries the number of keys destroyed, or that would be,
  over the documents the deletion deletes

#### Scenario: An original that was never encrypted

- **WHEN** a document whose original is stored as legacy plaintext is deleted
- **THEN** the deletion completes as before and the record counts zero keys

### Requirement: A key destroyed after the deletion is recorded

When a document that is already deleted is deleted again and still has a data
key that no other document that is not deleted needs, the system SHALL destroy
that key and SHALL append one audit record `deleted` to `deleted` carrying the
caller and the number of keys destroyed, and no key material. A repeated
deletion that destroys nothing SHALL append nothing.

#### Scenario: A document deleted before keys were destroyed

- **WHEN** a document that was deleted while its key row was left in place is
  deleted again
- **THEN** its key is gone, one new audit record says so with the count, and
  the hash chain still verifies

#### Scenario: Nothing left to destroy

- **WHEN** a deleted document without a key row is deleted again
- **THEN** no audit record is appended
