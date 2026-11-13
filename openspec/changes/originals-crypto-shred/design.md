# Design

## The step

`deletion.delete_document(session, document_id, store, index, *, actor,
dry_run=False, keys=None)`. `deletion.py` is 191 lines, so the key work lives
in a new module, `deletion_keys.py`, and `_object_claimed_elsewhere` moves
there with it (both the object removal and the key step use it).

```
former_key = doc.object_key                               # as today
doomed = deletion_keys.doomed(session, document_id, former_key)   # locks, see below
... index entry, object, text, pseudonyms, mappings, grants      # as today
counts.keys_destroyed = len(doomed)
if not dry_run and doomed:
    deletion_keys.destroy(session, doomed)                # SQL, same transaction
    if keys is not None:
        keys.evict(doomed)                                # this process's cache
... the audit record                                      # see "The record"
```

`doomed` runs first, before the index entry and the object are touched: it
takes the locks, and anything that can refuse a deletion must do so before
something irreversible has happened (the index and the object store are not
in the database transaction). The rows themselves are deleted after the
object removal and before the audit record.

## Who deletes the rows

`deletion_keys.destroy(session, object_keys) -> int` is a `DELETE` on
`document_keys` for those object keys. It needs a session and nothing else: no
Transit client, no `DocumentKeys`. A wrapped key that is deleted needs no
unwrapping.

That is why it is not a method on `DocumentKeys`, as the first amendment had
it. `wordsworth-delete` builds a plain `S3ObjectStore` and has no key service
configured; `delete_dossier` is called from there too. With the rows deleted
in SQL, every caller shreds, and none can skip the step for lack of a key
store. The earlier rule "`keys=None` with a key to destroy raises" is gone
with it: there is nothing left that a caller could be missing.

`keys` is optional and does one thing: `DocumentKeys.evict(object_keys)` drops
those entries from the unwrap cache of the process that ran the delete.
Correctness does not depend on it (see "The unwrap cache"); it saves that
process one failed lookup. If the transaction rolls back afterwards, the rows
are back and the cache misses once.

There is no configuration check in this step. If the build finds it needs one,
it goes with `doomed`, before the index and object removal.

## Which keys

`deletion_keys.doomed` returns the object keys of the `document_keys` rows
where

- `object_key == former_key`, or `document_id == document_id` (an
  OCR-recovered document has two sealed objects, the OCR'd PDF it points at
  and the scan it no longer points at; both rows carry its id,
  `originals-ocr-sealed`), and
- no other document row that is not deleted has that object key
  (`_object_claimed_elsewhere`, the check the object removal uses).

So the key goes when the object goes, and stays when the object stays.

Why not "the rows with this `document_id`", as the first version and the plan
for this amendment had it:

- The index `uq_documents_live_object_key` is partial (`WHERE superseded_by IS
  NULL`). A superseded copy has the same `object_key` as its survivor, and
  there is one key row per object key. If that row carried the copy's id,
  deleting the copy would destroy the survivor's key.
- A key row's `document_id` moves. `put_original` sets it to the live document
  when the same bytes are ingested again (rule 1) and does not touch it when it
  reseals a missing object under the existing row (rule 2). After a deleted
  document's bytes were ingested again under such a row, the row can carry the
  id of the deleted document while a live one reads through it.
- Selecting by `document_id` only would also miss a row that a re-ingest
  re-pointed at another document that has since been deleted.

The claim check covers all three, and it is the rule the object already
follows.

## Two deletions at once

A copy and its survivor share an object key. If both are deleted at the same
moment, each transaction sees the other document as not yet deleted, each
keeps the object and the key "for the other", and both commit: the object and
its key are left with no document.

`doomed` therefore first locks the `documents` rows that carry any of the
candidate object keys (`SELECT … FOR UPDATE`, ordered by id so two deletions
take them in the same order), and only then reads who still claims them. The
second deletion waits at the lock until the first commits, and then sees the
first document as deleted (READ COMMITTED: its next statement reads the
committed state). The object removal uses the same answer, so this also
closes the same gap for the object, which exists today.

## The record

- A document that is deleted now: `keys_destroyed` is one more count in
  `DeletionCounts.as_dict()` and so in the `deleted` record, as today's
  counts.
- A document that was **already deleted** when the call started: today a rerun
  writes no second record (`transition` is a no-op). If such a rerun destroys
  keys (`keys_destroyed > 0`), it appends one audit record `deleted` →
  `deleted` with step `destroy-key` and the payload `{actor,
  keys_destroyed}`, the way `release_deleted.release` records `release-key`.
  A key destroyed without a trace would be the one removal the audit trail
  does not show. A rerun that destroys nothing writes nothing, as today.
- This is also the path for documents deleted before this change: their key
  rows still carry their id, and running `wordsworth-delete` on them again
  destroys those keys with a record.
- A dossier: `DossierDeletionReport` gets `keys_destroyed`, the sum over the
  member documents it deleted (real or dry run), in `as_dict()` and so in the
  answer of `DELETE /dossiers/{id}` and the output of `wordsworth-delete
  --dossier`.

## The unwrap cache across replicas

`DocumentKeys` holds one cache per process (`self._cache`,
`document_keys.py:92`; read in `unwrap` at `:155`), and production runs two
API replicas. Evicting on the replica that ran the delete does nothing for the
other one.

`unwrap` therefore reads the key row from the database on every call, on the
hit path and on the miss path:

- **Hit.** It reads the row's `key_id` for that object key and uses the cached
  key only if a row exists and its `key_id` equals the cached key's. Otherwise
  the entry is dropped and `unwrap` continues as on a miss.
- **Miss.** It loads the row and unwraps through the key service, as today,
  and raises `OriginalsKeyUnavailable` when there is no row.
- **Both reads must reach the database.** Today's miss path uses
  `session.get`, which answers from the session's identity map when the row
  was loaded earlier in the same session, even if another transaction has
  deleted it since. Both paths use a `select` (a column select on the hit
  path, `populate_existing` on the miss path).
- **This relies on READ COMMITTED**, PostgreSQL's default and what the engine
  uses (`db.py` sets no isolation level): each statement sees what was
  committed before it started. Under REPEATABLE READ a long transaction would
  keep seeing the row. The docs say so, and a test pins the isolation level.
- Comparing `key_id`, not just existence, covers a key that was destroyed and
  minted again under the same object key (the bytes were ingested again): the
  old cached key must not open an old copy.
- Cost: one primary-key read per cached unwrap, on a session the caller
  already has. The cache still saves the call to OpenBao, which is what it is
  for.

## Failure

A failure in the step is a hard error (the existing rule): nothing after it
runs, no `deleted` record is written, the document stays in its state and a
rerun finishes the work.

## What does not change

- Legacy plaintext originals have no key row: `doomed` is empty,
  `keys_destroyed` is 0 and deletion behaves as today.
- The scan of an OCR-recovered document is not removed from the object store
  by deletion today, and this change does not add that. Once its key is
  destroyed it opens under no key row, which is what
  `wordsworth-sealed-orphans` lists and removes.
- The existing calls of `delete_document` in the tests keep their signature,
  because `keys` is optional: 12 in `tests/test_delete_documents.py` and 3 in
  `tests/test_console.py` (lines 109, 159, 205). Where one asserts the whole
  counts dictionary or the audit payload, `keys_destroyed` is added to the
  expectation; nothing else in them changes.

## Rejected

- **Destroying unconditionally by document id** (the first version): see
  "Which keys".
- **`DocumentKeys.destroy` deleting the rows** (the first amendment): see "Who
  deletes the rows".
- **A reference count on the key row**: the claim check already answers "does
  anyone else still need this object", from the rows themselves.
- **A shorter cache TTL instead of the row check**: it narrows the window and
  never closes it.
- **Telling the other replica to evict** (a notification): a second mechanism
  that can fail silently, for what one read settles.
- **An advisory lock per object key instead of row locks**: it works, but the
  rows are there to lock and a row lock needs no naming scheme.
