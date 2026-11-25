---
status: current
last_reviewed: 2026-11-25
---

# Lock order

Every transaction that writes about a document takes its locks in one order.
Two transactions that both follow it can wait for each other, but never in a
circle, so PostgreSQL has no deadlock to break. A new writer follows this
page; a writer that cannot is a finding, not an exception to add quietly.

## The order

| # | Lock | Mode | Taken by |
|---|------|------|----------|
| 1 | `documents` rows, by `id` when several | `FOR NO KEY UPDATE` by a writer that changes or removes the document; `FOR SHARE` by one that only needs it to stay as it is | deletion (`deletion_keys.doomed`), dossier deletion (`dossier_locks.lock_members`), supersession, dedupe, OCR recovery, `release_deleted.release`; `ingest` (`ingest_lock.lock_live`), the API's already-indexed path (`lock_live_for`), `process`, `reanonymize` and the pseudonym backfill (`lock_for_process`) |
| 2 | `document_keys` rows, by `object_key` | `FOR UPDATE` | deletion (`deletion_keys.doomed`) |
| 3 | the audit chain's advisory lock (key 4771) | `pg_advisory_xact_lock` | every `audit.append`; `audit.lock_chain` for a writer that decides something under it, and for the detection-feedback route, which takes it before it reads (#515) |
| 4 | `pii_mappings` rows, by `pseudonym` | inserted (`ON CONFLICT DO NOTHING`) and held `FOR KEY SHARE` by a run that stores or links them; `FOR UPDATE` by a deletion that removes them | `mapping_buffer.write_pending`, reached through `pseudonym_registry.link` (`process`, `reanonymize`, the pseudonym backfill) and called by the dataset run before its record; `deletion_mappings.remove` |

All of them last until the transaction ends. A writer holds its rows before
its first audit record, and writes or locks a `pii_mappings` row only once it
holds the chain lock. Reading one takes no lock and is outside the order: a
reveal reads mapping rows with a plain `SELECT` before its access record
takes the chain lock, and the pdf-redaction box map reads them the same
way; each statement sees what was committed when it started, and waits for
no writer. `audit.lock_chain` flushes the session before it locks, so a row
change that is still pending reaches the database before the chain lock and
not under it.

### The second chain: key lifecycle

`key_audit_pg.append` takes its own advisory lock (key 4772) for the
key-lifecycle stream: grants issued and revoked, role and group-role
changes, dossier renames, key rotations. It is taken last, after whatever
rows the change itself writes (the grant, role or dossier row, or the
mapping rows a rotation re-encrypts). No transaction takes it together with
the document chain lock (4771). A writer that would need both is a finding
to settle on this page first, not an order to improvise.

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
  `mapping_buffer.write_pending` stores the buffered rows once the chain lock
  is held, in pseudonym order. A row inserted earlier, uncommitted, was a
  lock ahead of the chain lock: two runs minting the same new values waited
  for each other in a circle (#504). It then holds the rows it linked `FOR
  KEY SHARE`. That is defence in depth: every deleter decides under the
  chain lock, which the linking run keeps until it commits, so the chain
  lock alone keeps the rows; the hold makes a `DELETE` outside that rule
  wait instead of succeed.
- **The chain lock also guards the link between a document and a mapping.**
  A deletion removes a mapping only when no other document is linked to it
  (`document_pseudonyms`), and decides that under the chain lock;
  `pseudonym_registry.link` stores the mappings and links under the same
  lock. So either the link is committed and the deletion sees it, or the
  deletion committed first and the linking run stores the mapping again
  (#465). Every caller that links goes through `link`.
- **A `put` is written explicitly, or the commit is refused.** Only
  `write_pending` (`mapping_buffer.py`) writes buffered rows; nothing writes them at commit. A
  caller that appends an audit record after its `put`s calls `write_pending`
  before that record (the dataset run), so the order on this page is visible
  in the code. An outermost commit with rows still buffered raises
  `UnwrittenMappings` -- loud, never a silent loss. The buffer ends with the
  outermost transaction (commit, rollback or `close`). A savepoint is not
  that: its release writes nothing and takes no lock, and its rollback drops
  nothing (`register_live` and `dossiers.add` roll one back on a lost race
  in the middle of a run). `write_pending` itself is refused inside a
  savepoint (`WriteInSavepoint`), whose rollback would take the stored rows
  and the chain lock with it.
- **Chain lock first, then read: only for a writer that waits for no row
  lock afterwards.** The detection-feedback route (`POST
  /documents/{id}/feedback`, #515) takes the chain lock, then reads the
  document's state, then appends. A deletion either committed first (the
  route answers 410 and appends nothing) or waits for the route's commit.
  The route does take one row lock under the chain lock: like every
  `audit.append`, its insert into `audit_records` takes `FOR KEY SHARE` on
  the `documents` row through the foreign key. That lock cannot wait, because
  it conflicts only with `FOR UPDATE` (or a key change or delete), and
  nothing takes `FOR UPDATE` on `documents`: writers take `FOR NO KEY
  UPDATE` or `FOR SHARE` (row 1), and no row is ever deleted. A writer that
  asks for any stronger row lock must take it before the chain lock, as
  above; so must anyone who would take `FOR UPDATE` on `documents`.
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
mapping rows, `tests/test_mapping_buffer.py` pins what commits, savepoints
and `close` do with buffered rows, and `tests/test_lock_chain_flush.py`
shows the flush in `audit.lock_chain` keeping a pending row change out from
under the chain lock. `tests/test_row_before_chain.py`
holds a row, lets the writer under test wait for it, and then appends an
audit record from the holder: a writer that took the chain lock first turns
that into a deadlock.
