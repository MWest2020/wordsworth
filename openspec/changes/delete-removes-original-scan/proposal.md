# delete-removes-original-scan

## Why

Issue #454 (found in the review of #453). When OCR recovers a scanned
document, `recover` writes the OCR'd PDF under its own content-addressed key,
points `documents.object_key` at it and records the scan's key only as
`old_object_key` in the payload of the `ocr` audit record
(`recovery.py:99-106`). The ocr spec says the scan object stays
(`openspec/specs/ocr/spec.md`, "the original scanned object SHALL NOT be
overwritten or deleted").

Deleting the document removes only the object its row points at, the OCR'd
PDF (`deletion.py:137-143`). The scan is the uploaded bytes, personal data in
the clear, and nothing in the system ever removes it:

- **A sealed scan** loses its key on deletion since `originals-crypto-shred`
  (its key row carries the document's id, `deletion_keys._candidate_rows`), so
  the object left behind is ciphertext under no key. It can still be opened
  from a database backup taken before the deletion (up to about 31 days, the
  how-to's "Limits"), and it stays in the store until someone runs
  `wordsworth-sealed-orphans --apply` by hand: no schedule runs it.
- **A legacy plaintext scan** (ingested before `originals-ingest-switch`,
  2026-11-09) has no key to destroy. It stays readable in the object store for
  good. This includes every recovered document deleted in the dossier cleanup
  of late October, when nothing was sealed yet. `originals-encrypt-existing`
  will not reach these either: it seals the object a live document points at,
  not a scan named only in an audit record.

Mark accepted the default on 2026-11-14 (mail, "defaults ok"): deleting a
document also removes its original scan object, and its key, counted in the
report, and a rerun cleans the leftovers.

## What changes

- Deleting a document (`DELETE /documents/{id}`, `wordsworth-delete`, a
  dossier deletion) also removes the object of each original scan its `ocr`
  audit record names, under the rule the main object already follows: **the
  object goes with its last claimant that is not deleted.** The scan's key, if
  it still has one, is destroyed by the step `originals-crypto-shred` already
  built, under the same rule.
- **A recovered document that is not deleted claims its scan.** Today a
  superseded copy that still has the scan's object key can be deleted while
  its recovered survivor is live, and that deletion removes the scan object
  and its key from under the survivor, against the ocr spec. With this change
  the claim check counts both: a document claims the object key its row points
  at, and the scan its `ocr` record names. The object removal, the key
  destruction and the new scan removal all use that one check, and the lock
  that serialises two deletions covers it.
- **Counts.** `DeletionCounts` gains `original_scan`: the number of scan
  objects removed (or, in a dry run, that would be). It appears in the
  `deleted` record, the API answer, the CLI output, and as a sum in
  `DossierDeletionReport`. `object` keeps its meaning (the object the row
  points at, 0 or 1); `keys_destroyed` already counts the scan's key.
- **A rerun cleans old deletions.** Deleting again a document that is already
  deleted removes a scan object that is still stored and no longer claimed,
  and appends one audit record `deleted` → `deleted` with step
  `remove-original-scan` and the payload `{actor, original_scan}`, as
  `destroy-key` and `remove-renders` do for their leftovers. A rerun that
  removes nothing appends nothing.
- **Operator step**, in the how-to: a read-only query that lists deleted
  documents whose scan no live document claims, then `wordsworth-delete
  --dry-run` and `wordsworth-delete` on those ids. Not part of the build.
- The ocr spec says recovery keeps the scan, and deletion removes it.

## Not here

- **Scans of documents that are not deleted** stay as they are. A legacy
  plaintext scan of a live recovered document stays plaintext; sealing it is a
  question for `originals-encrypt-existing` (see design.md, "Not here").
- **Database backups** still hold the wrapped key of a sealed scan for up to
  about 31 days; unchanged from `originals-crypto-shred`.
- **Copies of the object store** taken before the deletion still hold a
  legacy plaintext scan. Removing the object cannot reach them; that is the
  limit of plaintext, and the reason sealing exists.

## Depends on

`originals-crypto-shred` (built in #450, not yet archived). This change uses
its `deletion_keys.doomed` / `destroy` / `record_rerun` and adds requirements
next to its own in `document-deletion`. Archive `originals-crypto-shred`
first.
