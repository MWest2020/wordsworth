---
status: draft
last_reviewed: 2026-11-01
---

# Runbook: sealed orphans

`originals-cipher-and-key-store` seals every original PDF with its own data
key, recorded in a `document_keys` row. S3 and Postgres cannot share one
transaction, so an object can be written and then left behind when its
database transaction rolls back — the object exists, sealed, but no row names
its key (or a row exists but names a *different* key id, from an earlier
attempt). `wordsworth-sealed-orphans` finds and removes exactly these.

## Why they appear

A writer always writes the object *before* the caller commits the key row's
transaction. If the caller's commit then fails — a lost connection, a
conflicting transaction, a crash — the object is already there but the row
either never landed or landed for a different attempt. The bytes are
unreadable by construction (nobody has recorded a key for them, or the
recorded key does not match), so there is no plaintext risk in leaving them,
and the next write of the same bytes repairs the row-object pairing on its
own. The sweep exists to reclaim the storage, not to protect anything.

## What it does not touch

- a sealed object whose key row names its own key id (the normal case);
- a legacy plaintext object (no sealed header) — this sweep is about the
  sealed format only;
- any object younger than one hour, sealed or not — a write genuinely still
  in flight must never be mistaken for an orphan.

## Running it

```bash
wordsworth-sealed-orphans            # dry run: lists what it would remove
wordsworth-sealed-orphans --apply    # actually removes them
```

Dry run is the default and prints a JSON report of the keys found. `--apply`
removes exactly that list and reports which were actually removed (a key
already gone between the listing and the removal is not an error).

## Operational notes

- Safe to run repeatedly and on a schedule — it only ever removes bytes that
  no committed document can read.
- It lists under the `documents/` prefix only, via the object store's
  `iter_objects`, so it scales with the corpus, not with a directory listing
  outside the store.
- Until `originals-ingest-switch` lands, nothing in production writes a
  sealed object yet, so a dry run on a current deployment finds nothing. This
  command exists ahead of that change so it is in place and proven before
  anything depends on it.
