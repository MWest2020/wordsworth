# Proposal: delete-dossiers-topics

## Why

`wordsworth-delete --dossier` fails on 4 of the 10 old dossiers with a
`ForeignKeyViolation` on `topics_dossier_id_fkey`: the `topics` table still
refers to the dossier, so the dossier row cannot go. The transaction rolls back
cleanly, so nothing is half-deleted, but the operator gets a stack trace and the
dossier stays. `delete-dossiers` (archived) removed the memberships and the
dossier row and never considered the topics (`onderwerpen`) that hang off a
dossier. The same failure waits for `DELETE /dossiers/{id}`.

## What changes

- Deleting a dossier also removes the dossier's topics (the `topics` rows),
  in the same transaction, before the dossier row.
- The dry run reports the topics too, as a count, through the same code path.
- The report of the real run (API and CLI) carries the same topic count.
- Tested with a dossier that has topics, which `tests/test_delete_dossiers.py`
  did not have.

Decided in the channel: remove a dossier's topics along with it; the dry run
reports topics; test with a dossier that has topics. The alternative named in
the channel, refusing beforehand with a clear message, is not taken (see
design.md).

## Open questions

- Should removing topics leave an audit record? The `dossier-deleted` records
  are written per document, because `document_id` is a NOT NULL foreign key. A
  dossier with topics but no documents would leave no trace of its topics. Not
  decided; this change writes no new record kind.
- A released document stays indexed under its other dossiers and may still carry
  the removed topic ids in its index `topics` field. Whether that field must be
  cleaned on release is not decided here.
