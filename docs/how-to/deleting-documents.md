---
status: draft
last_reviewed: 2026-11-13
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
- the data key of its sealed original (crypto-shredding, below), unless the
  object stays because another document still claims it

What stays: the `documents` row and every earlier audit record. The audit
table's `document_id` is a non-null foreign key, and the trail never deletes a
record — removing the row would either break the trail or require deleting
audit records, the one thing this system never does (same reason a superseded
copy keeps its row). The document's state becomes `deleted`, terminal and
reachable from every state including `superseded`; nothing transitions out of
it.

One `deleted` audit record is written, holding the document id, the actor and
how many of each kind were removed (`keys_destroyed` among them) — never a
filename, a token, a value or key material.

**Deleting releases the object key.** The row's `object_key` becomes the
placeholder `deleted/<document-id>`, and the former key is recorded in the
`deleted` record as `released_object_key`. A deleted document therefore no
longer counts as *the* live document for its bytes: the same bytes can be
ingested again afterwards, which registers a new document while the deleted
one stays deleted with its trail unchanged. Documents deleted before this
behaviour existed still carry their real key until `wordsworth-release-
deleted-keys` (below) has run once.

## Crypto-shredding: the key goes with the document

An original stored sealed (ADR-0008) opens only with its data key, which
lives wrapped in the `document_keys` table. Deleting the document deletes
that row, in the same transaction as the rest of the deletion, with plain SQL
(`deletion_keys.py`). From then on every copy of the sealed object that
survives somewhere — a backup of the object store, a replicated volume — is
unreadable: there is no key left to open it with. The deletion does not need
the key service for this, so `wordsworth-delete` shreds exactly like the API.

**The key follows the object.** A key is destroyed exactly when the object is
removed: when no other document row that is not deleted still points at the
same object key. A superseded copy keeps the object key of its survivor, so:

- deleting the copy leaves the survivor's key (and object) alone;
- deleting the survivor while the copy is not deleted keeps the object and
  its key (`object: 0`, `keys_destroyed: 0`), and deleting the copy afterwards
  removes both (`object: 1`, `keys_destroyed: 1`).

This is the one case where deleting a document does not destroy its key at
once (decision #428, default: the key follows the object). A document
recovered by OCR has two sealed objects, the scan and the OCR'd PDF; it loses
both keys (`keys_destroyed: 2`). A legacy plaintext original has no key:
`keys_destroyed: 0`, and the deletion behaves as before.

A copy and its survivor deleted at the same moment do not each keep the key
"for the other": the deletion locks the document rows of that object key
first, so the second waits for the first and then sees it as deleted.

**On every replica at once.** Each API process caches unwrapped keys (up to
`WORDSWORTH_KEY_CACHE_TTL`, 300 s). The cache is not what makes the delete
hold: every unwrap reads the key row from the database, also on a cache hit,
and uses the cached key only while a row with the same key id exists. The
other replica therefore cannot open the object the moment the deletion
commits. This relies on PostgreSQL's default isolation level, READ COMMITTED
(each statement sees what was committed before it started); `db.py` sets no
other level, and a test pins it. Running the API under REPEATABLE READ would
let a long transaction keep seeing a destroyed row.

### Limits

- **Database backups hold wrapped keys** (decision #429). A backup of the
  database taken before the deletion still holds the deleted key row, wrapped
  by the KEK. With that backup, the KEK and a copy of the object, the original
  can be opened again until the backup expires. Crypto-shredding covers copies
  of the object store; it does not reach back into database backups. On the
  homelab cluster both database backups keep **30 days**: the daily
  `wordsworth-keys-backup` dump of `document_keys` (homelab runbook "Key
  backups") and the CNPG base backups plus WAL of `homelab-pg` (runbook "CNPG
  backup", `retentionPolicy: "30d"`). CNPG keeps the base backup it needs to
  restore any point in those 30 days, and that base backup can be up to a day
  older than the window. A deleted original can therefore still be opened from
  a database backup for up to about 31 days after the deletion, not only on
  the day itself.
- **A request already holding the key** when the deletion commits finishes
  with it; the next unwrap fails.
- **The dry run can undercount when a copy and its survivor are deleted
  together.** Each document's dry run looks at the others as they are now,
  not as the run would leave them. When a superseded copy and its survivor
  are both deleted in one run (both members of the dossier being deleted, or
  `wordsworth-delete A B --dry-run` with A and B a copy and its survivor), the
  dry run reports `object: 0` and `keys_destroyed: 0` for both, while the real
  run removes the object and destroys the key with the second of the two.
  The real run's output and the `deleted` records carry the true counts.

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
path as a real run, and stops before the first removal; `keys_destroyed` is
the number of data keys a real run would destroy, and every key still exists
afterwards. `--actor` is required
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
names out). Nothing changes and no record is written. `keys_destroyed` in the
dossier report, dry run and real, is the sum over the documents it deletes; a
released member keeps its key.

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

## Destroying keys of documents deleted before crypto-shredding

Documents deleted between the day sealing was switched on
(`originals-ingest-switch`) and the deployment of `originals-crypto-shred`
kept their key row. This query lists them — key rows whose document's latest
audit record is `deleted`:

```sql
SELECT k.document_id, k.object_key
FROM document_keys k
JOIN LATERAL (
  SELECT a.to_state FROM audit_records a
  WHERE a.document_id = k.document_id
  ORDER BY a.seq DESC LIMIT 1
) latest ON true
WHERE latest.to_state = 'deleted'
ORDER BY k.document_id;
```

Run `wordsworth-delete` on those ids again (dry run first):

```bash
wordsworth-delete <document-id> [...] --actor <who> --dry-run
wordsworth-delete <document-id> [...] --actor <who>
```

A rerun over an already-deleted document destroys any key it still has that
no other not-deleted document claims, and appends one audit record `deleted`
→ `deleted` with step `destroy-key` and the payload `{actor, keys_destroyed}`
— a count, never a key. A rerun with nothing to destroy appends nothing. A row
the query lists but another live document still reads through (it re-ingested
the same bytes) is left alone, and the output says `keys_destroyed: 0`. This
is an operator step after the deployment, not part of the build.

## What is not here

- **Un-deleting.** There is no restore path, by design.
