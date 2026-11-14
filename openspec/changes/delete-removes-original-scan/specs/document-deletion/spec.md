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
scan's data key, if it has one, SHALL be destroyed under the same claim, as
the key of any other object the deletion ends the last claim on. A scan that
is no longer in the object store SHALL count as 0 and SHALL NOT fail the
deletion. A failure to remove a scan SHALL be a hard error as any other failed
removal. No record SHALL carry a value, a filename or key material.

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

### Requirement: A recovered document that is not deleted claims its scan

Wherever a deletion decides whether another document still claims an object
key (for removing the object, destroying its key, or removing a scan), a
document SHALL count as claiming an object key when its row points at it or
when its recovering `ocr` audit record names it as the original scan. Two
deletions running at once whose documents claim the same object key either
way SHALL NOT each keep the object for the other.

#### Scenario: Deleting the copy keeps the scan of a live survivor

- **WHEN** a superseded copy whose object key is the scan of its recovered
  survivor is deleted while the survivor is not deleted
- **THEN** the scan object and its key still exist, and the copy's `deleted`
  record has `object: 0` and `keys_destroyed: 0`

#### Scenario: A copy and its recovered survivor are deleted at the same moment

- **WHEN** two deletions run at once, one for a superseded copy whose object
  key is the scan of its recovered survivor, and one for that survivor
- **THEN** after both have finished neither the scan object nor its key exists

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

#### Scenario: Nothing left to remove

- **WHEN** that document is deleted a third time
- **THEN** no audit record is appended

#### Scenario: The dry run over an old deletion

- **WHEN** the CLI runs with `--dry-run` on a document deleted before this
  change whose scan is still stored
- **THEN** it reports `original_scan: 1`, the scan is still stored and no
  record is appended
