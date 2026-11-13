# Design

## The step

`deletion.delete_document(session, document_id, store, index, *, keys, actor,
dry_run=False)` gains one step after the object removal and before the
`deleted` transition, in the same transaction. `deletion.py` is 191 lines, so
the step lives in a new module, `deletion_keys.py`, and
`_object_claimed_elsewhere` moves there with it (both the object removal and
the key step use it).

```
former_key = doc.object_key                       # as today
doomed = deletion_keys.doomed(session, document_id, former_key)
counts.keys_destroyed = len(doomed)
if not dry_run and doomed:
    keys.destroy(session, doomed)
```

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

## `DocumentKeys.destroy`

`destroy(session, object_keys) -> int` deletes the rows for those object keys,
removes them from this process's unwrap cache, and returns the number of rows
deleted. It makes no call to the key service: a wrapped key that is deleted
needs no unwrapping. If the transaction rolls back afterwards, the rows are
back and the cache simply misses once.

## The unwrap cache across replicas

`DocumentKeys` holds one cache per process (`document_keys.py:94`), and
production runs two API replicas. Evicting on the replica that ran the delete
does nothing for the other one.

`unwrap` therefore, on a cache hit, reads the row's `key_id` for that object
key and uses the cached key only if a row exists and its `key_id` equals the
cached key's. Otherwise the entry is dropped and `unwrap` continues as on a
miss, which raises `OriginalsKeyUnavailable` when there is no row.

- The read must reach the database: a `select` of `key_id`, not
  `session.get`, which can answer from the session's identity map.
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

`keys` is a required argument. A caller without a key service passes `None`;
if `doomed` is then not empty, the deletion raises instead of skipping the
step, so a deployment that has key rows can never delete a document and leave
its key.

## What does not change

- Legacy plaintext originals have no key row: `doomed` is empty,
  `keys_destroyed` is 0 and deletion behaves as today.
- The scan of an OCR-recovered document is not removed from the object store
  by deletion today, and this change does not add that. Once its key is
  destroyed it opens under no key row, which is what
  `wordsworth-sealed-orphans` lists and removes.
- `DeletionCounts.as_dict()` gains `keys_destroyed`; the `deleted` record and
  the dry run carry it through the existing paths.

## Rejected

- **Destroying unconditionally by document id** (the first version): see
  "Which keys".
- **A reference count on the key row**: the claim check already answers "does
  anyone else still need this object", from the rows themselves.
- **A shorter cache TTL instead of the row check**: it narrows the window and
  never closes it.
- **Telling the other replica to evict** (a notification): a second mechanism
  that can fail silently, for what one read settles.
