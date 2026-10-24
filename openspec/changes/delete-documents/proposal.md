# Delete a document, or a whole dossier, from wordsworth

## Why

Mark, via the odin coding session: *"definitely make a delete function,
especially in this development phase."* Today nothing in wordsworth removes a
document. The only retirement is `superseded`, which keeps the row, the text and
the index entry (`docs/reference/cli.md`, "A retired copy is not deleted").
During development, wrong or trial ingests (the 12-document pilot dossier is the
first) have no way out except editing the database by hand, and a hand edit
leaves no record.

This changes a promise: what the system keeps about a document, and who may make
it forget. So it is an OpenSpec change, not an issue.

## What changes

A new capability `document-deletion`:

- `DELETE /documents/{id}` and `DELETE /dossiers/{id}`.
- A CLI with `--dry-run`, which reports what would be removed and removes
  nothing.
- **Who may:** only a caller with role `beheerder`, or one carrying an issuer
  label. Everyone else is refused.
- **What goes**, per document: the stored object, the stored text, the
  pseudonyms, the mappings, the index entries and the grants.
- **What is written:** one append-only audit record `deleted`, with ids and
  counts, never values.
- **First use:** the 12-document pilot dossier.
- Tests and docs ship with it (see tasks.md).

The `document-lifecycle` capability gets one modified requirement: the state
machine gains the state `deleted` (see design.md for why it is a state).

## Non-goals

- Un-deleting. There is no restore path.
- Deleting audit records. The trail stays append-only; deletion adds to it.

## Open questions

- **The four audit-trail questions.** The orchestrator put four questions about
  the audit trail to the architect; their answers were not part of the decision
  recorded here. Nothing in this change should be read as answering them.
  Specifically, whether `deleted` carries anything beyond ids and counts is not
  decided.
- **How a caller is known to hold `beheerder`.** In the code today `beheerder`
  is a role name (`roles.ADMIN`) and issuer labels are a configured list
  (`grant_issuer_labels`); no mapping from an authenticated caller to a role
  exists yet. The decision says "role beheerder or an issuer label". This change
  does not say how the first half is determined.
- **A document that belongs to two dossiers.** Memberships are pairs, and the
  same bytes in two dossiers are one document. What `DELETE /dossiers/{id}` does
  to a document that also belongs to another dossier is not decided.
- **The dossier itself.** Whether `DELETE /dossiers/{id}` also removes the
  dossier row and its topics, or only the documents, is not decided.
- **The CLI's script name and arguments** are not decided; `wordsworth-dedupe`
  is the nearest precedent. Only the module, `wordsworth.delete_cli` with a
  `main`, is settled.
- **Deleting from an old index or backup** outside the live systems is not
  covered.
