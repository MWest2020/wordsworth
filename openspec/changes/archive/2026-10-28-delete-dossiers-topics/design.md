# Design: delete-dossiers-topics

## Delete the topics with the dossier

A topic belongs to exactly one dossier (`onderwerpen`: "A topic SHALL NOT span
dossiers") and holds only a description: name, computed time and a document
count. Membership lives in the search index, not in the `topics` table. So the
rows have no meaning once the dossier is gone, and deleting them loses no
content. They are removed in `dossier_deletion.delete_dossier`, after the
members are handled and before `session.delete(dossier)`, in the same
transaction. A failure anywhere still rolls back everything, and a rerun
finishes the work, as the `document-deletion` requirements already demand.

## Dry run through the same path

`DossierDeletionReport` gets a `topics` count. The count is computed in
`delete_dossier` before the `dry_run` return, so the dry run and the real run
cannot drift apart, as for documents. It is a count, not a list of names: topic
names are derived from document terms and the report rules keep names out.

## Rejected: refuse with a clear message

Refusing a dossier that has topics would turn a stack trace into a clear error
but would leave the operator removing topics by hand through a route that does
not exist. A dossier delete is already irreversible and already deletes its
documents, so deleting its descriptive topic rows is the smaller step.

## Rejected: ON DELETE CASCADE on the foreign key

It would need a migration and would remove topics silently, outside the code
path the dry run walks, so the dry run could not report them.
