## MODIFIED Requirements

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
