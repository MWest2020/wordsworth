## MODIFIED Requirements

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

## ADDED Requirements

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
