---
status: draft
last_reviewed: 2026-10-25
---

# Runbook: deleting a document

Today the only retirement is `superseded` (one-document-per-object), which
keeps the row, the text and the index entry — "a retired copy is not deleted"
(`docs/reference/cli.md`). This is the actual delete: during development a
wrong or trial ingest has no way out except a hand edit to the database, and a
hand edit leaves no record.

There is **no undo**. Deleting is a last resort, not a correction — if the
document is merely wrong for a dossier, remove the membership instead
(`dossiers.remove`); if it is a copy of one already here, retire it
(`wordsworth-dedupe`).

## What goes, what stays

Deleting a document removes:

- the stored object (unless another, not-yet-deleted document row still
  claims the same object key — a superseded copy keeps its former key)
- the stored (de-identified) text
- its pseudonyms, and the shared encrypted mapping underneath each one
  *unless* another document's pseudonyms still reference it (the mapping
  store is global — see [grants](grants.md))
- its search-index entry
- its grants scoped to this document

What stays: the `documents` row and every earlier audit record. The audit
table's `document_id` is a non-null foreign key, and the trail never deletes a
record — removing the row would either break the trail or require deleting
audit records, the one thing this system never does (same reason a superseded
copy keeps its row). The document's state becomes `deleted`, terminal and
reachable from every state including `superseded`; nothing transitions out of
it.

One `deleted` audit record is written, holding the document id, the actor and
how many of each kind were removed — never a filename, a token or a value.

## Who may

Only a caller with role `beheerder`, or one carrying a label in
`WORDSWORTH_GRANT_ISSUER_LABELS`, may delete. Anyone else is refused before
anything is read or removed, and a refusal writes no `deleted` record.

A caller **holds** `beheerder` by being the recipient of an active, unexpired
grant that names the role — the same fact [grants](grants.md) already uses to
resolve a role-granted reveal, read here as yes/no instead of a type set.
There is no separate identity-to-role table (see
[roles](roles.md#wat-hier-niet-woont)): "who someone is" comes from sign-on,
"what they may do" is decided here, at the one place every delete passes
through.

## Delete a document

```bash
curl -XDELETE $API/documents/<document-id>
```

404 for an unknown id, 403 for a caller who may not. The API has no dry run —
the CLI is where a human looks first.

## The CLI

```bash
wordsworth-delete <document-id> [<document-id> ...] --actor <who> --dry-run
wordsworth-delete <document-id> [<document-id> ...] --actor <who>
```

`--dry-run` reports the counts it would remove, using the exact same code
path as a real run, and stops before the first removal. `--actor` is required
and checked the same way as above; there is no implicit "whoever is running
this".

Each document commits on its own, like `wordsworth-dedupe` — a failure
partway through a multi-document run leaves only the untouched ones for a
rerun, and removing what a previous run already removed is a no-op (the state
is already `deleted`, the content already gone).

## A failed removal is a hard error

If any part fails — the index unreachable, a database error — the call fails,
no `deleted` record is written, and the document stays in its previous state.
A later call (the same `curl`, the same `wordsworth-delete`) finishes the work;
each content kind is removed only once, so repeating is safe.

## What is not here

- **Deleting a dossier.** `DELETE /dossiers/{id}` is not implemented. What it
  should do to a document that also belongs to another dossier, and whether it
  removes the dossier row itself, are open questions the proposal explicitly
  leaves undecided — this change does not guess them.
- **Un-deleting.** There is no restore path, by design.
