# Delete a dossier

## Why

`delete-documents` left one thing open: `DELETE /dossiers/{id}` was not built,
because two questions were undecided — what happens to a document that also
belongs to another dossier, and whether the dossier row itself goes
(`docs/how-to/deleting-documents.md`, "What is not here").

The orchestrator, from the odin coding session: *"Mark said 'everything open:
go', so the open question in deleting-documents.md (dossier deletion) is now
decided. I've used delete-documents: 203 documents outside the Gooise Meren
dossier are deleted (215 delete records in total). The Gooise Meren mappings
are intact (25,824 of 25,824). That leaves 10 empty dossier rows."*

Those 10 empty dossiers can only be removed by a hand edit to the database,
which leaves no record — the thing `delete-documents` exists to prevent.

This changes a promise (what is destroyed when a dossier goes, and what a shared
document is allowed to lose), so it is an OpenSpec change.

## What changes

- `DELETE /dossiers/{id}` and `wordsworth-delete --dossier <id> [--dry-run]`.
- The dossier's memberships and the dossier row are removed.
- A member document is deleted (as in `delete-documents`) only if it belongs to
  no other dossier; otherwise only its membership of this dossier is removed.
- One append-only `dossier-deleted` audit record per document touched, holding
  ids and counts, never names or values.
- The same guard as document deletion: role `beheerder` or an issuer label;
  anyone else is refused before anything is read or removed.
- A dry run reports exactly what the delete would do, by the same code path.
- Tests: a shared document, an empty dossier, a refused caller.
- Docs: `docs/how-to/deleting-documents.md` closes its open question;
  `docs/reference/cli.md` gains the `--dossier` option.
- Afterwards the 10 empty dossier rows are removed with it (an operator step,
  not part of the build).

## Open questions

- Whether each membership removal ALSO writes the membership-removal record that
  `dossiers` requires (with a reason), or whether `dossier-deleted` stands in
  for it. The decision names only `dossier-deleted`; this change adds nothing
  beyond it.
- An empty dossier touches no document, so it leaves no document-bound record.
  Whether its removal should be recorded in the key-lifecycle stream (as a
  rename is) was not decided.
- Whether an unknown dossier id answers 404 as an unknown document does. Not
  stated; no requirement is written for it.
