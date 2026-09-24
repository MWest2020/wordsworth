# Proposal: one live document per stored object

## Why

`object_key` is the sha256 of a document's bytes: "two uploads of the same
bytes under two names are one document" (`models.Document`). The database does
not enforce that. Registration is read-then-insert with no unique constraint,
and measured on 2026-09-24 production holds **791 documents over 618 distinct
`object_key`s**:

- **93 objects have copies**: 80 exist three times, 13 twice. 173 extra rows.
- **All of them date from 2026-08-17, 18 and 19**, three ingest runs of the
  same batch while the skip-if-already-ingested check was being built
  (`1dba54c`, `403a6f4`). Nothing has been duplicated since; the 203 documents
  of 2026-09-13 have no copies.
- **The copies are fully live.** They sit in dossiers (173 memberships, every
  one also held by the first copy), carry 18,595 pseudonym links, went through
  reprocessing, and **86 objects have 159 extra search-index entries**: a search
  can return the same document two or three times. No grant points at a copy.
- **The copies are interchangeable.** Ranked by registration, every rank has
  the same states: 80 `indexed`, 6 `indexed` with a failed reprocess, 7
  `unprocessable_ocr`.

The skip closes the door for sequential deliveries, but not for two at once,
and it reads the search index rather than the database. Two api replicas (since
hoge-beschikbaarheid step 2) make the concurrent case likelier.

## What Changes

- **A copy is retired, not deleted.** Every audit record points at its document
  with a required foreign key, and the trail is append-only; deleting a document
  would mean deleting its history. A new terminal state `superseded` records
  the retirement, with the surviving document as `superseded_by`.
- **A superseded document leaves the search index and its dossiers**, both
  as recorded acts. Its history, audit records and pseudonym links stay.
- **One-time cleanup command**, dry-run by default, that retires the 173
  copies in favour of the oldest registered copy of each object.
- **The database enforces the rule afterwards**: a unique index on
  `object_key` over documents that are not superseded. Registration that loses
  the race gets the existing document instead of a copy.

## Scope

**In:** the state, the cleanup, the constraint, and every reader that counts,
lists, searches or reveals by document.

**Out:** the 7 objects that stay `unprocessable_ocr` and the 6 whose reprocess
failed. They are real issues but not duplicates, and they are the same in
every copy.
