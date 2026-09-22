## ADDED Requirements

### Requirement: Changing what a scope returns leaves a trace

Adding or removing a membership SHALL be recorded in the append-only trail
against the document it concerns, naming the caller and the dossier.

A dossier decides what a scoped search answers, so moving a document changes what
someone can and cannot see. Without a record, the result is visible afterwards
and the act is not — and "who moved this, and when" is exactly the question asked
when something turns out to be missing.

Removing a membership SHALL carry a reason; adding one SHALL NOT require it.
Putting something somewhere can be reconstructed from the result; taking it away
cannot.

#### Scenario: A move is visible afterwards

- **WHEN** a document is removed from one dossier and added to another
- **THEN** the trail holds both events against that document, with the caller

#### Scenario: A removal without a reason is refused

- **WHEN** a membership is removed without a reason
- **THEN** it is refused and the membership stays

#### Scenario: Reading leaves nothing

- **WHEN** a dossier is searched
- **THEN** no record is written, because that is a different question with its
  own costs

### Requirement: A rename is recorded beside the documents, not on them

Renaming a dossier SHALL be recorded in the key-lifecycle stream, carrying the
old name, the new name, how many documents the dossier held at that moment, and
the caller. It SHALL NOT write a record against any document.

A rename moves no document and changes no membership; it changes a label that a
thousand documents share. A record per document would fill the chain with
copies of one fact, and a single record without a document does not fit a table
whose key is the document. The stream that already carries grants, key
rotations and role changes is where document-less authorisation facts belong —
the same reasoning `roles.py` records for roles.

The count is the reason the record exists: it says how far one act reached,
without writing it once per document.

#### Scenario: Renaming touches no document chain

- **WHEN** a dossier holding documents is renamed
- **THEN** no audit record is appended against any of those documents

#### Scenario: The record says how far it reached

- **WHEN** a dossier holding 791 documents is renamed
- **THEN** the stream event carries the old name, the new name and that count

### Requirement: One act is readable as one act

Membership records written by a single bulk operation SHALL share an identifier
for that operation.

A backfill that assigns 791 documents is honest as 791 records — every document
really did get a membership. Without something binding them, a day of history
reads as hundreds of unrelated decisions, and a trail nobody can read is a trail
that does not do its job.

#### Scenario: A backfill is one action in the trail

- **WHEN** one command assigns many documents to dossiers
- **THEN** every record it writes carries the same batch identifier

#### Scenario: A single change needs no batch

- **WHEN** one document is moved by hand
- **THEN** no batch identifier is required
