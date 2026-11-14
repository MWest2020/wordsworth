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
dossier's memberships, the dossier's topics and the dossier itself, under the
same authorisation. A member document SHALL be deleted as described above only
if it belongs to no other dossier; a document that belongs to another dossier
SHALL lose only its membership of this one. The topics SHALL be removed in the
same transaction as the dossier, so that a dossier with topics is deleted
instead of failing on them.

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

#### Scenario: A dossier with topics

- **WHEN** a dossier that has topics is deleted
- **THEN** the deletion succeeds, the dossier and its topics no longer exist,
  and the topics of other dossiers are unchanged

#### Scenario: A failed deletion keeps the topics

- **WHEN** a dossier deletion fails part-way
- **THEN** the dossier and its topics are still there, and a later call
  completes the deletion

### Requirement: A dry run changes nothing

The deletion CLI SHALL accept `--dry-run`, which reports what would be removed,
as counts, and SHALL NOT remove anything or write an audit record. On a dossier
it SHALL report exactly what the delete would do, by the same code path: which
documents would be deleted, which would only lose their membership, and how
many topics would be removed.

#### Scenario: Dry run

- **WHEN** the CLI runs with `--dry-run` on a dossier
- **THEN** it prints the counts, every store is unchanged and no `deleted`
  record exists

#### Scenario: The dry run matches the real run

- **WHEN** the CLI runs with `--dry-run` on a dossier and then without
- **THEN** the documents the real run deleted and the documents it only
  released are exactly those the dry run reported

#### Scenario: The dry run reports topics

- **WHEN** the CLI runs with `--dry-run` on a dossier that has topics
- **THEN** the number of topics is printed, no topic is removed, and the real
  run then removes that same number

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

### Requirement: A deleted document releases its object key

Deleting a document SHALL, in the same transaction as its `deleted` record,
replace its `object_key` by the placeholder `deleted/<document id>` and record
the former key in that record. The check whether the stored object may be
removed SHALL use the former key. A deleted document SHALL NOT count as the
live document for its former bytes.

#### Scenario: The key is released

- **WHEN** a document is deleted
- **THEN** its row carries `deleted/<document id>` and its `deleted` record
  carries the former key

#### Scenario: The same bytes can be ingested again

- **WHEN** the bytes of a deleted document are ingested again
- **THEN** a new document is registered and the deleted one stays deleted with
  its trail unchanged

#### Scenario: A failed deletion keeps the key

- **WHEN** a deletion fails before it completes
- **THEN** the row keeps its former key, no `deleted` record exists, and a rerun
  completes the deletion and releases the key

### Requirement: Documents deleted earlier can be released

`wordsworth-release-deleted-keys` SHALL list deleted documents that still carry
a content key and, with `--apply`, release each as a deletion does, writing one
audit record per document. It SHALL NOT touch a document that is not deleted.

#### Scenario: One-off release

- **WHEN** the command runs with `--apply` and then again
- **THEN** the first run releases every such document with one audit record each
  and the second finds none

### Requirement: A data key is destroyed with the last claim on its object

A deletion SHALL destroy a data key exactly when it ends the last claim on that
key's object: when no other document that is not deleted still claims the same
object key. A document claims an object key when its row points at it, or when
its recovering `ocr` audit record names it as its original scan. The removal of
an object, the removal of an original scan and the destruction of a key SHALL
all use this one claim. A document with more than one sealed object SHALL lose
the key of each, whichever document id the key row carries. Two deletions
running at once whose documents claim the same object key, either way, SHALL
NOT each keep the object or its key for the other. Every caller of a deletion
SHALL destroy keys in the same way, whether or not it has a key service. The
`deleted` record and the dry run SHALL carry the number of keys destroyed, a
dossier deletion SHALL report their sum, and none of them SHALL carry key
material. A failure to destroy a key SHALL be a hard error as any other failed
removal: no `deleted` record, the document in its previous state. An original
that was never encrypted has no key, and its deletion SHALL behave as before.

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

#### Scenario: Deleting a copy keeps the scan of a live survivor

- **WHEN** a superseded copy whose object key is the scan of its recovered
  survivor is deleted while the survivor is not deleted
- **THEN** the scan object and its key still exist, and the copy's `deleted`
  record has `object: 0` and `keys_destroyed: 0`

#### Scenario: Deleting a re-ingest keeps the scan of a live recovered document

- **WHEN** the scan's bytes of a recovered document were ingested again as a
  new document, and that new document is deleted while the recovered document
  is not deleted
- **THEN** the scan object and its key still exist, and the new document's
  `deleted` record has `object: 0` and `keys_destroyed: 0`

#### Scenario: The scan's key row carries another document's id

- **WHEN** the scan's bytes of a recovered document were ingested again as a
  new document (so the scan's key row carries the new document's id), the new
  document is deleted, and the recovered document is deleted afterwards
- **THEN** after the second deletion the scan object and its key row are both
  gone

#### Scenario: A copy and its recovered survivor are deleted at the same moment

- **WHEN** two deletions run at once, one for a superseded copy whose object
  key is the scan of its recovered survivor, and one for that survivor, with
  the scan sealed or stored as legacy plaintext
- **THEN** after both have finished neither the scan object nor its key exists

#### Scenario: A dossier deletion with a recovered member and a copy on its scan

- **WHEN** a dossier is deleted whose members include a recovered document,
  while a superseded copy with a lower id whose object key is that document's
  scan is deleted at the same moment
- **THEN** neither deletion deadlocks, and after both the scan object and its
  key are gone

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

### Requirement: Deleting a document removes its original scan

Deleting a document that was recovered by OCR SHALL also remove the object of
each original scan its recovering `ocr` audit record names, in the same
deletion as its own object, when no other document that is not deleted claims
that scan. Deleting through `DELETE /documents/{id}`, through
`wordsworth-delete` and as a member of a deleted dossier SHALL all do this. The
`deleted` record, the API answer, the CLI output and the dry run SHALL carry
the number of scan objects removed (or that would be) as `original_scan`, and
a dossier deletion SHALL report the sum over the documents it deletes. The
scan's data key, if it has one, SHALL be destroyed under the same claim,
whichever document id its key row carries. A scan that is no longer in the
object store SHALL count as 0 and SHALL NOT fail the deletion. A failure to
remove a scan SHALL be a hard error as any other failed removal. No record
SHALL carry a value, a filename or key material.

#### Scenario: A recovered document

- **WHEN** a document recovered by OCR, with a sealed scan and a sealed OCR'd
  PDF, is deleted
- **THEN** neither object is in the object store, both keys are gone, and the
  `deleted` record has `object: 1`, `original_scan: 1` and
  `keys_destroyed: 2`

#### Scenario: A legacy plaintext scan

- **WHEN** a document whose scan is stored as legacy plaintext, without a key
  row, is deleted after OCR recovery
- **THEN** the scan object is gone, `original_scan` is 1, and
  `keys_destroyed` counts only the key of the OCR'd PDF

#### Scenario: The scan is already gone

- **WHEN** a recovered document is deleted whose scan is no longer in the
  object store
- **THEN** the deletion completes, `original_scan` is 0 and no error is raised

#### Scenario: A superseded copy still has the scan's object key

- **WHEN** a recovered document is deleted while a superseded copy that is not
  deleted still has the scan's object key, and that copy is deleted afterwards
- **THEN** after the first deletion the scan object and its key still exist
  and `original_scan` is 0, and after the second both are gone with
  `object: 1` and `keys_destroyed: 1` for the copy

#### Scenario: The scan's bytes were ingested again

- **WHEN** a recovered document is deleted after its scan's bytes were
  ingested again as a document that is not deleted
- **THEN** the scan object and its key stay and `original_scan` is 0

#### Scenario: A dossier deletion

- **WHEN** a dossier is deleted that holds a recovered document belonging to
  no other dossier, and a recovered document that also belongs to another
  dossier
- **THEN** the first document's scan is gone, the second keeps its scan, and
  the dossier report's `original_scan` is 1

#### Scenario: The dry run counts the scan

- **WHEN** the CLI runs with `--dry-run` on a recovered document whose scan is
  stored
- **THEN** it reports `original_scan: 1`, the scan object and its key still
  exist, and no audit record is written

#### Scenario: Removing the scan fails

- **WHEN** the object store fails while removing the scan during a deletion
- **THEN** the call fails, no `deleted` record exists, and a later call
  completes the deletion and removes the scan

### Requirement: A scan removed after the deletion is recorded

When a document that is already deleted is deleted again and its original scan
is still stored and claimed by no other document that is not deleted, the
system SHALL remove the scan object and SHALL append one audit record
`deleted` to `deleted` with step `remove-original-scan`, carrying the caller
and `original_scan`, and no value or key. Any key destroyed or render removed
by the same rerun SHALL keep its own record. A repeated deletion that removes
no scan SHALL append no `remove-original-scan` record. Earlier audit records
SHALL stay unchanged.

#### Scenario: A document deleted before this change

- **WHEN** a recovered document that was deleted while its scan object was
  left in the store, and whose scan key was already destroyed, is deleted
  again
- **THEN** the scan object is gone, one `remove-original-scan` record with
  `original_scan: 1` is appended, no `destroy-key` record is appended, and the
  hash chain still verifies

#### Scenario: Each leftover keeps its own record

- **WHEN** a deleted document whose scan object, scan key row and a cached
  render are all still there is deleted again
- **THEN** exactly one `remove-original-scan`, one `destroy-key` and one
  `remove-renders` record are appended, each with only its own counts, and the
  hash chain still verifies

#### Scenario: Nothing left to remove

- **WHEN** that document is deleted a third time
- **THEN** no audit record is appended

#### Scenario: The dry run over an old deletion

- **WHEN** the CLI runs with `--dry-run` on a document deleted before this
  change whose scan is still stored
- **THEN** it reports `original_scan: 1`, the scan is still stored and no
  record is appended
