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
| 4 | `pii_mappings` rows, by `pseudonym` | `FOR UPDATE` by a deletion that removes them; `FOR KEY SHARE` by a run that links them | `deletion_mappings.remove`; `pseudonym_registry.link` (`mapping_store.pin`) |

All of them last until the transaction ends. Nothing lower in the table is
asked for while waiting would mean holding something higher that another
writer needs first: a writer holds its rows before its first audit record,
and touches a mapping row's lock only once it holds the chain lock.

## What follows from it

- **Several documents in one transaction: lock them all first.** The first
  audit record takes the chain lock and keeps it. A dossier deletion
  therefore locks every member, and every row sharing their objects, before
  it deletes the first one (#460, #462); `wordsworth-dedupe` locks every copy
  of an object before it retires the first (#466).
- **Flush a row change before appending.** `audit.append` takes the chain
  lock with a plain statement, which does not flush the session; a pending
  `UPDATE documents` would then reach the database after the chain lock.
  `release_deleted.release` locks the row, flushes its change, and only then
  appends (#466).
- **Adding to an existing document needs its row.** A deletion decides what
  it removes once it holds the rows. Whoever adds something to a document
  without going through `ingest` -- the API's already-indexed path adding a
  dossier membership -- locks the row `FOR SHARE` and checks that the
  document is still live (`ingest_lock.lock_live_for`), or the addition lands
  on a document that is being deleted (#466).
- **The chain lock also guards the link between a document and a mapping.**
  `pii_mappings` is global: one value is one token everywhere. A deletion
  removes a mapping only when no other document is linked to it
  (`document_pseudonyms`), and decides that under the chain lock; `process`
  and `reanonymize` link under the same lock. So either the link is
  committed and the deletion sees it, or the deletion committed first and
  the linking run stores the mapping again (`mapping_store.pin`) (#465).
- **A reader that waited reads again.** Under READ COMMITTED a statement
  after the wait sees what the other transaction committed. `reanonymize`
  returns the state it found; `reprocess` reports a document that was
  deleted in between as `skipped` with the reason `deleted`, not as
  `reanonymized` (#469).
- **A dry run takes no lock** and waits for nothing.

## Known exception

The anonymizer stores a mapping (`PostgresMappingStore.put`, an
`INSERT ... ON CONFLICT DO NOTHING`) while it anonymizes, which is before
`reanonymize` -- or a `process` resumed from `extracted` -- holds the chain
lock. A `process` that started from `registered` holds the chain lock from
its first record on. When both mint the same value that has no mapping yet,
the first holds the new row and waits for the chain lock, the second holds
the chain lock and waits for the row: PostgreSQL aborts one of them with
`DeadlockDetected`. Nothing is lost -- the aborted run wrote nothing and a
rerun finishes it -- but it is an error where a wait would do. Closing it
means holding the chain lock while anonymizing in those two paths too, which
makes a backfill block every other audit record for as long as each document
takes; that trade-off is open in #504.

Key rotation (`mapping_store.reencrypt`) updates mapping rows without the
chain lock. It is an operator action; do not run it beside deletions.

## Testing a lock order

The race tests hold one side at a known point with a `threading.Event`, start
the other, and wait until PostgreSQL reports a session waiting on a lock
(`tests/race_setup.py`, `wait_for_a_lock_waiter`) before letting go -- a
fixed interleaving, no sleeps to tune. `tests/test_row_before_chain.py`
holds a row, lets the writer under test wait for it, and then appends an
audit record from the holder: a writer that took the chain lock first turns
that into a deadlock.
