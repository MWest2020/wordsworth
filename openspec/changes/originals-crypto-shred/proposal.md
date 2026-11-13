# originals-crypto-shred

## Why

ADR-0008: deleting a document must make its original unreadable everywhere,
including in backups and replicas that still hold the object. Destroying the
document's data key does that (crypto-shredding).

## What changes

- Deleting a document (document or dossier deletion) destroys the wrapped data
  key of every object the deletion ends the last claim on, in addition to
  removing the object, in the same transaction.
- The key rows are deleted by the deletion itself, with SQL, in a new module
  `deletion_keys.py`. That needs no key service, so every caller can do it,
  including `wordsworth-delete`, which has a plain object store and no
  Transit client. `DocumentKeys` (which has `mint` and `unwrap` only today)
  gets `evict`, to drop the destroyed keys from the unwrap cache of the
  process that ran the delete.
- **The delete holds on every replica at once.** `DocumentKeys` caches
  unwrapped keys per process and production runs two API replicas, so today
  the other replica could still open a surviving copy until
  `WORDSWORTH_KEY_CACHE_TTL` (300 seconds) runs out. `unwrap` therefore
  confirms that the key row still exists, with the same key id, before it
  trusts a cached key: one primary-key read, no call to the key service. This
  check, not the eviction, is what makes the delete hold everywhere.
- **A key follows its object.** The key is destroyed exactly when the object
  is removed: when no other document row that is not deleted still points at
  that object key. A superseded copy shares its object key with its survivor,
  so deleting the copy leaves the survivor's key alone.
- `deletion.delete_document` takes an optional `keys` (a `DocumentKeys`), used
  only for that local eviction. `api.py` passes the one it has;
  `delete_cli.py` has none and passes nothing; `dossier_deletion.py` passes on
  what it was given.
- The `deleted` audit record counts the destroyed keys (never a key).
- Dry run reports how many keys would be destroyed, for a document and, as a
  sum, for a dossier (`DossierDeletionReport.keys_destroyed`, in the API
  answer and the CLI output).
- Deleting again a document that is already deleted destroys any key it still
  has and records that: this is how documents deleted before this change lose
  their key.
- A copy and its survivor deleted at the same moment cannot each keep the key
  for the other: the claim check locks the document rows of that object key.

## Amended 2026-11-13

The first version called the step "unconditional" because
`uq_documents_live_object_key` "allows only one live document per object key".
That index is **partial** (`WHERE superseded_by IS NULL`): it says nothing
about superseded copies, which keep the object key of their survivor
(`models.py:23`, `deletion._object_claimed_elsewhere`). The step is therefore
conditional, on the same check the object removal already uses. Also added:
nothing in the code could destroy a key, `delete_document` had no way to
reach the key cache, and the unwrap cache made the scenario "that copy can no longer be
decrypted" false on the second replica for up to five minutes.

Two points differ from the plan for this amendment, which named
`DocumentKeys.destroy(session, document_id)`. After review, the rows are
deleted in `deletion_keys.py` and `DocumentKeys` only evicts (see above): a
method on `DocumentKeys` would leave `wordsworth-delete` unable to shred. And
the selection is by **object key**, not by document id. A key row's
`document_id` is not a reliable owner. `put_original` re-points it at the live
document on a re-ingest (`originals_store.py`, rule 1) and leaves it alone on a
reseal (rule 2), and two document rows can share one object key. Selecting by
document id alone would either destroy a survivor's key or leave a key behind.
See design.md.

## Working assumptions (Mark can overrule)

- **Shredding is immediate across replicas**, at the price of one extra
  primary-key read on every cached unwrap. Decided in the product plan as a
  working assumption. The alternative is to accept a window of
  `WORDSWORTH_KEY_CACHE_TTL` and say so in the docs.
- **The key lives as long as the object does.** When a deleted document's
  object is kept because a superseded copy that is not deleted still points at
  it, the key is kept with it, and is destroyed when the last such row is
  deleted. This follows what deletion already does with the object; it is not a
  new rule, but it is the one case where "deleting a document destroys its
  key" is not immediate, so it is named here.

## Limits (stated in the docs, not solved here)

- A **database** backup taken before the deletion still holds the wrapped key.
  With that backup, the KEK and a copy of the object, the original can be
  opened until the database backup expires. Crypto-shredding covers copies of
  the object store; it does not reach back into database backups. The how-to
  says so and names the retention.
- Documents deleted between the day sealing was switched on and the day this
  change is deployed keep their key row until someone deletes them again. The
  how-to gives the query that lists them and says to run `wordsworth-delete`
  on those ids; it is an operator step, not part of the build.
- A request that already holds an unwrapped key when the delete commits
  finishes with it.

## Depends on

`originals-ocr-sealed` (the chain `originals-cipher-and-key-store` →
`deleted-document-releases-object-key` → `originals-ingest-seam` → `originals-ingest-readers` → `originals-ingest-write` → `originals-ingest-switch` →
`originals-ocr-sealed`, which replaced `originals-envelope-encryption`). All
are built and archived.
