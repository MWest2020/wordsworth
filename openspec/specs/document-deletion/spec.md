# document-deletion Specification

## Purpose
Created by the change `delete-documents`. Mark, via the odin coding session: *"definitely make a delete function,

## Requirements

### Requirement: Only a beheerder or an issuer label may delete

`DELETE /documents/{id}`, `DELETE /dossiers/{id}` and the deletion CLI SHALL
allow only a caller with role `beheerder` or an issuer label. Any other caller
SHALL be refused before anything is read or removed, and a refusal SHALL NOT
write a `deleted` audit record.

#### Scenario: A beheerder deletes

- **WHEN** a caller with role `beheerder` deletes a document
- **THEN** the document is deleted

#### Scenario: An issuer label deletes

- **WHEN** a caller carrying an issuer label deletes a document
- **THEN** the document is deleted

#### Scenario: Anyone else is refused

- **WHEN** any other caller deletes a document
- **THEN** the answer is 403, nothing is removed and no `deleted` record exists

### Requirement: Deleting a document removes its content

Deleting a document SHALL remove its stored object, its stored text, its
pseudonyms, its mappings, its index entries and its grants. The `documents` row
and the document's earlier audit records SHALL remain.

#### Scenario: Nothing of the content is left

- **WHEN** an indexed document is deleted
- **THEN** its object, text, pseudonyms, mappings, index entries and grants are
  gone, and a search no longer returns it

#### Scenario: The trail is kept

- **WHEN** a document is deleted
- **THEN** its earlier audit records and the hash chain are unchanged and still
  verify

### Requirement: A deletion is an append-only audit record

Deleting a document SHALL append one audit record `deleted`, in the same
transaction as the removal. The record SHALL hold ids and counts and SHALL NOT
hold any value, text, token or filename.

#### Scenario: The record has counts, not values

- **WHEN** a document is deleted
- **THEN** one `deleted` record exists with the document id, the caller and the
  count removed of each kind, and no value appears in it

### Requirement: A failed removal is a hard error

When any part of a deletion fails, the system SHALL report the error, SHALL NOT
write the `deleted` record and SHALL leave the document in its previous state.
Repeating the deletion SHALL finish the work.

#### Scenario: The index is down

- **WHEN** the search index is unavailable during a deletion
- **THEN** the call fails, no `deleted` record exists, and a later call with a
  healthy index completes the deletion

### Requirement: A dossier can be deleted

`DELETE /dossiers/{id}` and `wordsworth-delete --dossier <id>` SHALL remove the
dossier's memberships and the dossier itself, under the same authorisation. A
member document SHALL be deleted as described above only if it belongs to no
other dossier; a document that belongs to another dossier SHALL lose only its
membership of this one.

#### Scenario: A dossier with several documents

- **WHEN** a dossier of several documents is deleted
- **THEN** each of its documents has a `deleted` record and no content

#### Scenario: A shared document keeps its content

- **WHEN** a dossier is deleted that holds a document which also belongs to
  another dossier
- **THEN** that document keeps its content and its other membership, and only
  its membership of the deleted dossier is gone

#### Scenario: An empty dossier

- **WHEN** a dossier without documents is deleted
- **THEN** the dossier no longer exists and no document is changed

#### Scenario: A refused caller

- **WHEN** a caller who is neither beheerder nor an issuer label deletes a
  dossier
- **THEN** the answer is 403, the dossier and its memberships remain and no
  record is written

### Requirement: A dry run changes nothing

The deletion CLI SHALL accept `--dry-run`, which reports what would be removed,
as counts, and SHALL NOT remove anything or write an audit record. On a dossier
it SHALL report exactly what the delete would do, by the same code path: which
documents would be deleted and which would only lose their membership.

#### Scenario: Dry run

- **WHEN** the CLI runs with `--dry-run` on a dossier
- **THEN** it prints the counts, every store is unchanged and no `deleted`
  record exists

#### Scenario: The dry run matches the real run

- **WHEN** the CLI runs with `--dry-run` on a dossier and then without
- **THEN** the documents the real run deleted and the documents it only
  released are exactly those the dry run reported

### Requirement: A dossier deletion is recorded per document touched

Deleting a dossier SHALL append one `dossier-deleted` audit record for each
document it touched, whether the document was deleted or only lost its
membership. The record SHALL hold ids and counts and SHALL NOT hold a name, a
value, a text, a token or a filename.

#### Scenario: Deleted and released documents both leave a record

- **WHEN** a dossier is deleted that holds one exclusive and one shared
  document
- **THEN** each of the two has a `dossier-deleted` record with the document id,
  the dossier id and the caller, and no value appears in either
