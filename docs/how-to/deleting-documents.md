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
- its cached redacted PDFs (every object under `redacted/<document-id>/`) and
  its box map (the `box_maps` row they were drawn from)
- its summary (the `document_summaries` row: LLM text derived from the
  document, see [summaries](#the-summary-of-a-deleted-document))
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

**Deleting releases the object key.** The row's `object_key` becomes the
placeholder `deleted/<document-id>`, and the former key is recorded in the
`deleted` record as `released_object_key`. A deleted document therefore no
longer counts as *the* live document for its bytes: the same bytes can be
ingested again afterwards, which registers a new document while the deleted
one stays deleted with its trail unchanged. Documents deleted before this
behaviour existed still carry their real key until `wordsworth-release-
deleted-keys` (below) has run once.

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

## The redacted PDF of a deleted document

`GET /documents/{id}/redacted.pdf` caches each render in the object store
under `redacted/<document-id>/<render-version>/<boxmap-hash>`. A deletion
removes every object under that prefix and the `box_maps` row, and counts
them as `renders_removed` and `box_maps_removed` — in the `deleted` record,
the API answer and the CLI output (a dry run counts them and removes nothing).
The renders are listed before anything irreversible happens: if listing
fails (say the S3 identity lacks `ListObjectsV2`), the deletion fails with
nothing removed and the document in its previous state.

For a deleted document, `GET /documents/{id}/redacted.pdf` and
`POST /documents/{id}/reveal.pdf` answer **410 Gone**, checked before the
cache is looked at: a render left behind is never served. 410 rather than
404 because the id is known and its absence is deliberate and permanent;
404 stays "unknown id", 409 stays "not yet / stale, `reanonymize` fixes it".

**Leftovers.** Documents deleted before #451 kept both, and a request that was
rendering while the deletion committed can still write one object afterwards.
To find them (read-only):

```sql
-- box_maps rows whose document is deleted
SELECT b.document_id
FROM box_maps b
JOIN LATERAL (
  SELECT a.to_state FROM audit_records a
  WHERE a.document_id = b.document_id
  ORDER BY a.seq DESC LIMIT 1
) latest ON true
WHERE latest.to_state = 'deleted'
ORDER BY b.document_id;

-- every deleted document id, to feed the dry run below
SELECT d.id
FROM documents d
JOIN LATERAL (
  SELECT a.to_state FROM audit_records a
  WHERE a.document_id = d.id
  ORDER BY a.seq DESC LIMIT 1
) latest ON true
WHERE latest.to_state = 'deleted'
ORDER BY d.id;
```

The `redacted/` objects live in the object store, not in a table, so a query
cannot list them; the dry run does, by the same prefix the deletion uses. Run
it over the deleted ids — it removes nothing and writes no record — and every
result with `renders_removed` or `box_maps_removed` above 0 is a leftover:

```bash
wordsworth-delete <deleted-id> [...] --actor <who> --dry-run
```

To clean them, run the same command without `--dry-run` on those ids. A rerun
over an already-deleted document removes the leftover objects and row and
appends one audit record `deleted` → `deleted` with step `remove-renders` and
the payload `{actor, renders_removed, box_maps_removed, summaries_removed}`
(the summary below rides on the same record); with nothing left it appends
nothing.

After a partial failure, the record the rerun writes (`deleted`, or
`remove-renders` on an already-deleted document) counts only what was still
there: renders, an index entry or an object the failed attempt already removed
from outside the database are not counted again, so the counts can be lower
than what the document once had.

## The summary of a deleted document

A summary (`document_summaries`, written by `summaries.py`) is text a language
model derived from the document's content, so it goes with that content. A
deletion removes the row and counts it as `summaries_removed` (0 or 1) — in
the `deleted` record, the API answer and the CLI output; a dry run counts it
and removes nothing. The text itself never appears in a count or a record. A
deleted document has no text left, so no summary is made for it afterwards.

**Leftovers.** Documents deleted before #455 kept their summary. It was no
longer served (the index entry was gone), but it still held derived content.
To find them (read-only):

```sql
-- document_summaries rows whose document is deleted
SELECT s.document_id
FROM document_summaries s
JOIN LATERAL (
  SELECT a.to_state FROM audit_records a
  WHERE a.document_id = s.document_id
  ORDER BY a.seq DESC LIMIT 1
) latest ON true
WHERE latest.to_state = 'deleted'
ORDER BY s.document_id;
```

Clean them the same way as the renders above: `wordsworth-delete <id> [...]
--actor <who>` over those ids (`--dry-run` first shows `summaries_removed: 1`).
The rerun appends the same `remove-renders` record, `deleted` → `deleted`,
whose payload now carries all three counts:
`{actor, renders_removed, box_maps_removed, summaries_removed}`. Records
written before #455 lack `summaries_removed`.

## A failed removal is a hard error

If any part fails — the index unreachable, a database error — the call fails,
no `deleted` record is written, and the document stays in its previous state.
A later call (the same `curl`, the same `wordsworth-delete`) finishes the work;
each content kind is removed only once, so repeating is safe.

## Delete a dossier

```bash
curl -XDELETE $API/dossiers/<dossier-id>
wordsworth-delete --dossier <dossier-id> --actor <who> [--dry-run]
```

Removes the dossier's memberships, the dossier's topics and the dossier row.
A member document is deleted, as above, only if it belongs to no other
dossier; one that belongs to another dossier too keeps its content and loses
only its membership of this one — deleting one case must not silently empty
another. The topics (`onderwerpen`) are removed in the same transaction, so a
dossier that has topics is deleted instead of failing on
`topics_dossier_id_fkey`.

One `dossier-deleted` audit record is written per document the deletion
touched, whether it was deleted or only released: the document id, the
dossier id, the actor and which of the two happened — never a name or a
value. A document that is also deleted gets its usual `deleted` record too
(above).

Who may: the same guard as deleting a document — only role `beheerder` or an
issuer label, refused before anything is read or removed, no record on a
refusal.

`--dry-run` walks the same code path and reports exactly what the real run
would do: which documents would be deleted, which would only lose their
membership, and how many topics would be removed (a count, not a list of
names — topic names are derived from document terms and the report keeps
names out). Nothing changes and no record is written.

## Releasing keys of documents deleted before this change

```bash
wordsworth-release-deleted-keys            # lists what it would release
wordsworth-release-deleted-keys --apply    # releases them
```

Run this once after deploying `deleted-document-releases-object-key`. It
finds every document that is, right now, `deleted` and still carries a real
object key, and with `--apply` releases each the same way a deletion does:
one `release-key` audit record per document, holding `released_object_key`.
Idempotent — a released document is not found again — and it never touches a
document that is not deleted.

## What is not here

- **Un-deleting.** There is no restore path, by design.
