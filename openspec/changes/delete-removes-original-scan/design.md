# Design

## Where the scan lives today

- **Object key.** `documents/<sha256 of the scan bytes>`, the key the
  document had at ingest. `recover` keeps it in `old_key` and repoints
  `documents.object_key` at the OCR'd PDF (`recovery.py:100-102`). After that
  the scan's key is written down in one place only: the payload of the
  recovering audit record, `step = 'ocr'`, `unprocessable_ocr` →
  `extractable`, field `old_object_key` (`recovery.py:104-107`). No column
  holds it. A document is recovered at most once (`recover` refuses any state
  but `unprocessable_ocr`, and nothing transitions back into it), but the code
  below reads "every scan the document's `ocr` records name" and does not
  assume one.
- **Sealed or not.** A scan ingested after `originals-ingest-switch`
  (production 2026-11-09) was written sealed by `write_original` with a key row
  carrying the document's id. A scan ingested before that is a legacy
  plaintext object without a key row; recovery never reseals it
  (`originals-ocr-sealed` seals only the OCR'd PDF).
- **Its key at deletion, today.** `deletion_keys.doomed` takes the candidate
  key rows `object_key == former_key OR document_id == document_id`
  (`deletion_keys._candidate_rows`), so a sealed scan whose row still carries
  the document's id loses its key: the how-to's `keys_destroyed: 2`, test
  `test_shred_deletion` "a document recovered by OCR loses 2 keys". The
  `originals-crypto-shred` design says so explicitly: "The scan of an
  OCR-recovered document is not removed from the object store by deletion
  today, and this change does not add that."
- **Its object at deletion, today.** Not touched. `delete_document` removes
  `former_key` only (`deletion.py:137-143`).
- **Risk left behind.**
  - Sealed scan, key destroyed: ciphertext under no key row. Readable only
    with a database backup from before the deletion (about 31 days) plus the
    KEK. `wordsworth-sealed-orphans --apply` would remove it (it opens under
    no key row), but nothing schedules that command (no reference in the
    homelab repo).
  - Sealed scan deleted before `originals-crypto-shred` was deployed: key row
    still present until the `destroy-key` rerun in the how-to has run.
  - Legacy plaintext scan: clear personal data, permanently, in every copy of
    the object store. Every recovered document deleted before 2026-11-09 (the
    dossier cleanup of late October included) is in this group.

## The claim

One question decides the object, its key and now the scan: does a document
other than this one, that is not deleted, claim this object key?

A document **claims** an object key when

1. its row points at it (`documents.object_key`), as today; or
2. its `ocr` record names it as `old_object_key` (new).

`deletion_keys._object_claimed_elsewhere(session, document_id, object_key)`
gets the second clause. Both the main object removal and `doomed` already
call it, so the object, the key and the scan follow one rule.

What the second clause changes for existing behaviour, and only this: a
superseded copy whose `object_key` is the scan of a recovered survivor (the
copy was retired while the survivor still had the scan's key; the survivor
was recovered afterwards). Today deleting that copy while the survivor is
live removes the scan object and destroys its key, against the ocr spec.
With the clause the scan and its key stay until the survivor is deleted too.
`object` and `keys_destroyed` for that copy's deletion become 0.

Query for clause 2:

```python
select(AuditRecord.document_id).where(
    AuditRecord.step == "ocr",
    AuditRecord.to_state == State.EXTRACTABLE.value,
    AuditRecord.payload["old_object_key"].astext == object_key,
    AuditRecord.document_id != document_id)
```

then `current_state(...) != DELETED` on each, as clause 1 does. No index is
added: `audit_records` has none on `step` or the payload, deletions are rare
and operator-driven, and the corpus is in the hundreds to low thousands. The
clever pitfall here would be adding a `documents.scan_key` column to make the
lookup cheap: a second copy of a fact the trail already holds, which a
backfill has to get right for every old row. If deletions ever get slow, a
partial expression index `ON audit_records ((payload->>'old_object_key'))
WHERE step = 'ocr'` is the follow-up, not a column.

## Which scans

`deletion_scans.scan_keys(session, document_id) -> list[str]`: the distinct
`old_object_key` values of the document's `ocr` records with `to_state =
'extractable'`, minus `former_key` (handled as the object), sorted.

A scan is **removable** when `store.exists(scan_key)` and not
`_object_claimed_elsewhere(session, document_id, scan_key)`.
`original_scan` is the number of removable scans.

## Locks

`doomed` locks the `documents` rows of every candidate object key, ordered by
id, so a copy and its survivor deleted at once serialise. With the claim
widened, the lock must widen with it, or two deletions can again each keep
the scan "for the other": the copy (whose row points at the scan) and its
recovered survivor (whose `ocr` record names it) have different
`object_key`s, so today's lock set of the copy does not include the survivor.

In the locking statement of `doomed`:

- the candidate object keys gain the document's scan keys (`scan_keys`);
- the rows locked are those with `id == document_id`, or `object_key` among
  the candidates (as today), or that have an `ocr` record naming one of the
  candidates as `old_object_key` (new; a subquery on `audit_records`).

Still one statement, `FOR NO KEY UPDATE`, ordered by id, so the deadlock
analysis of `originals-crypto-shred` (an audit append's KEY SHARE) holds.
The re-read-and-repeat loop on `former_key` stays as it is: scan keys come
from the append-only trail and cannot change under the lock.

## The step

`deletion.py` is 200 lines, the limit. The scan work lives in a new module
`deletion_scans.py` (`scan_keys`, `plan`, `record_rerun`), and `deletion.py`
calls it in one place. To make room, `DeletionCounts` may move next to
`RenderCounts` (`deletion_renders.py`) or into the new module; `deletion.py`
keeps re-exporting it, since tests and `dossier_deletion.py` import it from
there.

```
former_key, doomed = deletion_keys.doomed(...)          # locks, incl. scan claimants
... index entry                                          # as today
... object (former_key), if removable                    # as today
scans = deletion_scans.plan(session, document_id, former_key, store)   # new
counts.original_scan = len(scans)
if not dry_run: for key in scans: store.delete(key)      # new
... renders, text, pseudonyms, mappings, grants          # as today
... key rows (doomed already holds the scan's key)       # as today
... the record(s)                                        # see below
```

The scan goes with the object, after the index entry and before the DB-only
work: same place, same failure semantics. A failure removing it propagates
(hard error, no `deleted` record, the document in its previous state); a
rerun recomputes and finishes, and counts only what was still there, as the
how-to already says of partial failures.

## The output contract

`original_scan` (int) is added to `DeletionCounts.as_dict()`, after
`object`. It is therefore in the `deleted` record payload, the answer of
`DELETE /documents/{id}` and each document's line of `wordsworth-delete`.
`DossierDeletionReport` gets `original_scan`, the sum over the documents the
dossier deletion deleted (real and dry run), in `as_dict()`, so in the answer
of `DELETE /dossiers/{id}` and the output of `wordsworth-delete --dossier`.
A released member keeps its scan and adds nothing.

Rejected: `object: 2`. `object` is 0 or 1 today and means "the object this
row points at"; making it 2 for one kind of document breaks every reader that
treats it as a flag, and hides which of the two went. A separate count is
additive: a reader that does not know it ignores it.

No object key and no value goes into a record because of this change; the
scan's key stays where it already is, in the `ocr` record.

## Reruns and old deletions

A rerun over a document that was already deleted when the call started:

- removes each removable scan and, when it removed at least one, appends one
  audit record `deleted` → `deleted`, step `remove-original-scan`, payload
  `{actor, original_scan}`;
- destroys a key it still finds and records `destroy-key` as today;
- removes leftover renders and records `remove-renders` as today.

Each leftover kind keeps its own step and payload, the pattern the how-to
already documents ("two records, each with its own step and payload"). A
rerun that removes nothing appends nothing. All appends are new records; no
record is changed.

For a document deleted after `originals-crypto-shred` was deployed the scan's
key is already gone, so the rerun writes `remove-original-scan` only. For one
deleted before it, with a sealed scan whose row is still there, it writes
`destroy-key` and `remove-original-scan`. For a legacy plaintext scan,
`remove-original-scan` only.

## Operator step and the production count

SQL sees the database, not the object store, so the query lists candidates
and the dry run decides. Read-only; for the main session to run against
production once, and for the how-to.

```sql
-- Deleted documents whose original scan no document that is not deleted
-- still claims (by object_key, or as the scan of its own OCR record).
WITH state AS (
  SELECT d.id AS document_id, d.object_key, latest.to_state
  FROM documents d
  JOIN LATERAL (
    SELECT a.to_state FROM audit_records a
    WHERE a.document_id = d.id
    ORDER BY a.seq DESC LIMIT 1
  ) latest ON true
),
scans AS (
  SELECT DISTINCT a.document_id, a.payload->>'old_object_key' AS scan_key
  FROM audit_records a
  WHERE a.step = 'ocr' AND a.to_state = 'extractable'
    AND a.payload ? 'old_object_key'
),
leftover AS (
  SELECT s.document_id, s.scan_key, (k.object_key IS NOT NULL) AS key_row
  FROM scans s
  JOIN state st ON st.document_id = s.document_id AND st.to_state = 'deleted'
  LEFT JOIN document_keys k ON k.object_key = s.scan_key
  WHERE NOT EXISTS (
          SELECT 1 FROM state o
          WHERE o.object_key = s.scan_key AND o.to_state <> 'deleted')
    AND NOT EXISTS (
          SELECT 1 FROM scans s2
          JOIN state o ON o.document_id = s2.document_id
          WHERE s2.scan_key = s.scan_key
            AND s2.document_id <> s.document_id
            AND o.to_state <> 'deleted')
)
SELECT document_id, scan_key, key_row FROM leftover ORDER BY document_id;
```

The count for #454 is the same query with the last line replaced by:

```sql
SELECT count(*)                            AS deleted_with_unclaimed_scan,
       count(*) FILTER (WHERE key_row)     AS key_row_still_present,
       count(*) FILTER (WHERE NOT key_row) AS no_key_row,
       (SELECT count(*) FROM scans s JOIN state st USING (document_id)
         WHERE st.to_state <> 'deleted')   AS live_recovered_documents
FROM leftover;
```

plus one sanity check that the trail names every scan (expected 0):

```sql
SELECT count(*) FROM audit_records
WHERE step = 'ocr' AND to_state = 'extractable'
  AND NOT payload ? 'old_object_key';
```

Reading the result:

- `key_row_still_present`: sealed scans of documents deleted before
  `originals-crypto-shred`; the `destroy-key` rerun already covers their key.
- `no_key_row`: either a sealed scan whose key is destroyed (ciphertext) or a
  legacy plaintext scan (clear). SQL cannot tell them apart and cannot tell
  whether the object still exists. `wordsworth-sealed-orphans` (dry run, the
  default) lists the sealed ones without a key row; a `scan_key` from this
  list that the store holds and the sweep does not list is plaintext. After
  this change, `wordsworth-delete <ids> --dry-run` reports `original_scan: 1`
  for every one still stored, sealed or not.

The how-to's operator step is: run the list query, then
`wordsworth-delete <ids> --actor <who> --dry-run`, then the same without
`--dry-run`. Each removal appends `remove-original-scan`.

## What does not change

- The OCR'd PDF is the document's object and goes as today; its key too.
- A legacy plaintext original that was never scanned: no `ocr` record,
  `original_scan` is 0, nothing new happens.
- A copy retired by OCR (`supersede(..., as_object=new_key)`) keeps its own
  scan as its `object_key` and has no recovering `ocr` record: its scan is its
  object and goes by the existing path.
- `recover` itself does not change.
- The dry run's known undercount when a copy and its survivor are deleted in
  one run applies to `original_scan` as it does to `object` and
  `keys_destroyed`.

## Not here

- Sealing the plaintext scan of a document that is **not** deleted.
  `originals-encrypt-existing` seals "each live document with a legacy
  plaintext original", i.e. its `object_key`; a recovered document's scan is
  not its `object_key`, so that change as written leaves those scans
  plaintext. Named in the PR as a question for that change, not solved here.
- A schedule for `wordsworth-sealed-orphans`.

## Rejected

- **`object: 2`**: see "The output contract".
- **A `documents.scan_key` column**: see "The claim".
- **Deleting the scan at recovery time**: the ocr spec keeps the scan on
  purpose (provenance, re-OCR), and Mark's default is about deletion.
- **Leaving it to `wordsworth-sealed-orphans`**: it never touches plaintext,
  and a sealed scan would still sit there until someone runs it by hand.
- **Ignoring scan claims** (removing the scan whenever the document is
  deleted): breaks when a copy or a re-ingest still points at the scan's
  bytes, and leaves today's copy-deletion bug in place.
