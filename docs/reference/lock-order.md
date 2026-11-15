---
status: current
last_reviewed: 2026-11-15
---

# Lock order

Every transaction that writes about a document takes its locks in one order.
Two transactions that both follow it can wait for each other, but never in a
circle, so PostgreSQL has no deadlock to break. A new writer follows this
page; a writer that cannot is a finding, not an exception to add quietly.

## The order

| # | Lock | Mode | Taken by |
|---|------|------|----------|
| 1 | `documents` rows, by `id` when several | `FOR NO KEY UPDATE` by a writer that changes or removes the document; `FOR SHARE` by one that only needs it to stay as it is | deletion (`deletion_keys.doomed`), dossier deletion (`dossier_locks.lock_members`), supersession, dedupe, OCR recovery, `release_deleted.release`; `ingest` (`ingest_lock.lock_live`), the API's already-indexed path (`lock_live_for`), `process` and `reanonymize` (`lock_for_process`) |
| 2 | `document_keys` rows, by `object_key` | `FOR UPDATE` | deletion (`deletion_keys.doomed`) |
| 3 | the audit chain's advisory lock | `pg_advisory_xact_lock` | every `audit.append`; `audit.lock_chain` for a writer that decides something under it |
| 4 | `pii_mappings` rows, by `pseudonym` | inserted (`ON CONFLICT DO NOTHING`) and held `FOR KEY SHARE` by a run that stores or links them; `FOR UPDATE` by a deletion that removes them | `mapping_store.write_pending`, reached through `pseudonym_registry.link` (`process`, `reanonymize`, the pseudonym backfill), from the dataset run, and at commit for anything still buffered; `deletion_mappings.remove` |

All of them last until the transaction ends. A writer holds its rows before
its first audit record, and reads, writes or locks a `pii_mappings` row only
once it holds the chain lock. `audit.lock_chain` flushes the session before
it locks, so a row change that is still pending reaches the database before
the chain lock and not under it.

## What follows from it

- **Several documents in one transaction: lock them all first.** The first
  audit record takes the chain lock and keeps it. A dossier deletion
  therefore locks every member, and every row sharing their objects, before
  it deletes the first one (#460, #462); `wordsworth-dedupe` locks every copy
  of an object before it retires the first (#466).
- **Lock the row before the record, and read it again.** A writer that
  only set an attribute and appended took the chain lock first and asked for
  the row under it. `release_deleted.release` locks the row, checks that the
  key is still the one it was sent for, and then appends (#466).
- **Adding to an existing document needs its row.** A deletion decides what
  it removes once it holds the rows. Whoever adds something to a document
  without going through `ingest` -- the API's already-indexed path adding a
  dossier membership -- locks the row `FOR SHARE` and checks that the
  document is still live (`ingest_lock.lock_live_for`), or the addition lands
  on a document that is being deleted (#466).
- **`pii_mappings` is written under the chain lock, never before.** The
  table is global: one value is one token everywhere. An anonymizer meets
  values in text order, long before its run holds the chain lock, so
  `PostgresMappingStore.put` only buffers the row on the session.
  `mapping_store.write_pending` stores the buffered rows once the chain lock
  is held, in pseudonym order. A row inserted earlier, uncommitted, was a
  lock ahead of the chain lock: two runs minting the same new values waited
  for each other in a circle (#504).
- **The chain lock also guards the link between a document and a mapping.**
  A deletion removes a mapping only when no other document is linked to it
  (`document_pseudonyms`), and decides that under the chain lock;
  `pseudonym_registry.link` stores the mappings and links under the same
  lock. So either the link is committed and the deletion sees it, or the
  deletion committed first and the linking run stores the mapping again
  (#465). Every caller that links goes through `link`.
- **A `put` is not lost.** Whatever is still buffered when a transaction
  commits is stored then, the same way; a rollback drops it. A caller that
  appends an audit record after its `put`s calls `write_pending` before
  that record (the dataset run), so the order on this page is visible in
  the code and not left to the commit.
- **A reader that waited reads again.** Under READ COMMITTED a statement
  after the wait sees what the other transaction committed. `reanonymize`
  returns the state it found; `reprocess` counts a document that was deleted
  in between as `skipped`, not as `reanonymized`, and logs a
  `reprocess_skipped` line with that state (#469).
- **A dry run takes no lock** and waits for nothing.

## Known exceptions

- **Key rotation** (`mapping_store.reencrypt`) updates mapping rows without
  the chain lock. It is an operator action; do not run it beside deletions.
- **A dossier deletion's later members.** A single deletion's text and grant
  rows are deleted before it takes the chain lock. A dossier deletion holds
  the chain lock from its first member's record on, so for members 2..n
  those rows are asked for under it (#512).
- **The `dossiers` row is not in the order yet.** Adding a membership takes
  a key-share lock on it (the foreign key) and then appends; a dossier
  deletion appends first and deletes the row last (#510).

## Testing a lock order

The race tests hold one side at a known point with a `threading.Event`, start
the other, and wait until PostgreSQL reports a session waiting on a lock
(`tests/race_setup.py`, `wait_for_a_lock_waiter`) before letting go -- a
fixed interleaving, no sleeps to tune. `tests/test_mapping_write_order.py` does it for the
mapping rows. `tests/test_row_before_chain.py`
holds a row, lets the writer under test wait for it, and then appends an
audit record from the holder: a writer that took the chain lock first turns
that into a deadlock.
