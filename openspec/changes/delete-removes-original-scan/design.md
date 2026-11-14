# Design

## Where the scan lives today

- **Object key.** `documents/<sha256 of the scan bytes>`, the key the
  document had at ingest. `recover` keeps it in `old_key` and repoints
  `documents.object_key` at the OCR'd PDF (`recovery.py:100-102`). After that
  the scan's key is written down in one place only: the payload of the
  recovering audit record, `step = 'ocr'`, `unprocessable_ocr` →
  `extractable`, field `old_object_key` (`recovery.py:104-107`). No column
  holds it. A document is recovered at most once (`recover` refuses any state
  but `unprocessable_ocr`, and only `registered` leads into it), but the code
  below reads "every scan the document's `ocr` records name" and does not
  assume one.
- **Sealed or not.** A scan ingested after `originals-ingest-switch`
  (production 2026-11-09) was written sealed by `write_original` with a key row
  carrying the document's id. A scan ingested before that is a legacy
  plaintext object without a key row; recovery never reseals it
  (`originals-ocr-sealed` seals only the OCR'd PDF).
- **Its key row's `document_id` moves.** `put_original` re-points a key row at
  the newest live document when the same bytes are ingested again (rule 1). So
  after the scan's bytes are ingested again as a new document, the scan's key
  row carries that document's id, not the recovered document's.
- **Its key at deletion, today.** `deletion_keys.doomed` takes the candidate
  key rows `object_key == former_key OR document_id == document_id`
  (`deletion_keys._candidate_rows`), so a sealed scan whose row still carries
  the document's id loses its key: the how-to's `keys_destroyed: 2`, test
  `test_shred_deletion` "a document recovered by OCR loses 2 keys". A scan
  whose row was moved to another document is not a candidate, and its key
  survives (see "Which keys").
- **Its object at deletion, today.** Not touched. `delete_document` removes
  `former_key` only (`deletion.py:137-143`). The `originals-crypto-shred`
  design says so: "The scan of an OCR-recovered document is not removed from
  the object store by deletion today, and this change does not add that."
- **Risk left behind.**
  - Sealed scan, key destroyed: ciphertext under no key row. Readable only
    with a database backup from before the deletion (about 31 days) plus the
    KEK. `wordsworth-sealed-orphans --apply` would remove it (it opens under
    no key row), but nothing schedules that command (no reference in the
    homelab repo).
  - Legacy plaintext scan: clear personal data, permanently, in every copy of
    the object store. Every recovered document deleted before 2026-11-09 (the
    dossier cleanup of late October included) is in this group.
- **Production, 2026-11-14** (the read-only count in "Operator step", run by
  the main session): **6** deleted documents whose scan no live document
  claims, **all 6 without a key row**; **0** live recovered documents; the
  sanity check (recovering `ocr` records without `old_object_key`) is **0**.
  All six were deleted before sealing could have covered their scan, so they
  are expected to be legacy plaintext; the dry run after deployment confirms
  which are still stored.

## The claim

One question decides the object, its key and now the scan: does a document
other than this one, that is not deleted, claim this object key?

A document **claims** an object key when

1. its row points at it (`documents.object_key`), as today; or
2. its `ocr` record names it as `old_object_key` (new).

`deletion_keys._object_claimed_elsewhere(session, document_id, object_key)`
gets the second clause. Both the main object removal and `doomed` already
call it, so the object, the key and the scan follow one rule. In the spec
this is a MODIFIED version of `originals-crypto-shred`'s requirement "A data
key is destroyed with the last claim on its object", not a second rule beside
it.

The second clause changes existing behaviour in exactly two cases, both
while the recovered document A (scan S) is not deleted:

- **A superseded copy C whose `object_key` is S** (C was retired while A
  still had S; A was recovered afterwards). Today deleting C removes S and
  destroys its key, against the ocr spec. With the clause S and its key stay;
  C's `object` and `keys_destroyed` become 0.
- **A re-ingest N of S's bytes** (after A's recovery, S is no longer A's
  `object_key`, so the same bytes register as a new live document N with
  `object_key` S). Today deleting N removes S and destroys its key, the row of
  which `put_original` had moved to N. With the clause S and its key stay
  while A lives; N's `object` and `keys_destroyed` become 0.

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

`deletion_scans.scan_keys(session, document_ids) -> set[str]`: the distinct
`old_object_key` values of the documents' `ocr` records with `to_state =
'extractable'`. For one document, minus its `former_key` (handled as the
object). `doomed`, `lock_members` and the scan removal all use this one
helper, so the three sets cannot drift apart.

A scan is **removable** when `store.exists(scan_key)` and not
`_object_claimed_elsewhere(session, document_id, scan_key)`.
`original_scan` is the number of removable scans.

## Which keys

`deletion_keys._candidate_rows` becomes

```
object_key == former_key
OR document_id == document_id
OR object_key IN scan_keys(document_id)        -- new
```

The third clause is needed because the scan's key row can carry another
document's id. The sequence that defeats crypto-shred without it: A is
recovered with scan S; S's bytes are ingested again as N, which moves S's key
row to N; N is deleted while A lives, so S and its key stay (correct, by the
claim); then A is deleted. S is removed, but its key row (`document_id = N`)
is not a candidate, and survives. With the clause it is a candidate, no live
document claims S, and the row goes with the object.

The claim check then decides, as for every other candidate: the scan's key
goes exactly when the scan object goes.

## Locks

`doomed` locks the `documents` rows of every candidate object key, ordered by
id, so two deletions of documents that share a claim serialise. With the
claim widened, the lock set must widen with it.

The race this closes: copy C (`object_key` S) and its recovered survivor A
(whose `ocr` record names S) have different `object_key`s. When S is sealed
and its key row still carries A's id, today's sets already serialise them:
S is a candidate of A through the key row, so A's set contains C's row, and
C always locks its own row. When S is legacy plaintext (no key row), or its
key row was moved to another document, A's set does not contain C's row and
C's does not contain A's: both deletions see the other document as not
deleted, both keep S "for the other", and S (and any key) is left with no
claimant. The widened set closes both cases.

### `doomed`, per document

In its one locking statement (`FOR NO KEY UPDATE`, ordered by id):

- the candidate object keys are `{former_key}` ∪ the object keys of the
  candidate key rows (now including `scan_keys`) ∪ `scan_keys`;
- the rows locked are those with `id == document_id`, or `object_key` among
  the candidates (as today), or that have a recovering `ocr` record whose
  `old_object_key` is among the candidates (new; a subquery on
  `audit_records` matching that whole set: candidates ∪ {`former_key`} ∪
  `scan_keys`).

The re-read-and-repeat loop on `former_key` stays: scan keys come from the
append-only trail and cannot change under the lock.

### `lock_members`, per dossier (#462)

`dossier_locks.lock_members` must lock up front exactly the set `doomed` will
lock for each member; its docstring says why: once member 1's `deleted`
record holds the chain's advisory lock, any row lock `doomed` takes for member
2 that was not taken up front breaks "row lock first, advisory lock after",
and a copy with a lower id deadlocks with a concurrent deletion of that copy
(the #462 deadlock). The widened `doomed` would bring it back.

So `_object_keys` adds `scan_keys(session, document_ids)` (and, through it,
the key rows whose `object_key` is one of those scans), and the locking
statement adds the rows that have a recovering `ocr` record naming any key in
the set, in the same one statement ordered by id. Its repeat-while-changed
loop is unchanged. `doomed`'s lock for each member is then re-entrant, as
today. The docstring of `dossier_locks.py` is updated to name the scan.

Both statements stay `FOR NO KEY UPDATE`, so the `originals-crypto-shred`
deadlock analysis (an audit append's KEY SHARE) holds.

## The step

`deletion.py` is 200 lines, the limit. The scan work lives in a new module
`deletion_scans.py` (`scan_keys`, `plan`, `record_rerun`), and `deletion.py`
calls it in one place. To make room, `DeletionCounts` may move next to
`RenderCounts` (`deletion_renders.py`) or into the new module; `deletion.py`
keeps re-exporting it, since tests and `dossier_deletion.py` import it from
there.

```
former_key, doomed = deletion_keys.doomed(...)   # locks incl. scan claimants;
                                                 # doomed now includes the scan's
                                                 # key row whatever id it carries
... index entry                                  # as today
... object (former_key), if removable            # as today
scans = deletion_scans.plan(session, document_id, former_key, store)   # new
counts.original_scan = len(scans)
if not dry_run: for key in scans: store.delete(key)                    # new
... renders, text, pseudonyms, mappings, grants  # as today
... key rows in doomed                           # as today
... the record(s)                                # see below
```

The scan goes with the object, after the index entry and before the DB-only
work: same place, same failure semantics. A failure removing it propagates
(hard error, no `deleted` record, the document in its previous state); a
rerun recomputes and finishes.

**The rerun gap**, the same as for `remove-renders`: the object store is not
in the transaction. If the scan is removed and the commit then fails, the
removal is real but unrecorded, and the rerun counts only what is still there
(`original_scan: 0`). The how-to's paragraph on partial failures covers it;
it names the scan.

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
`destroy-key` and `remove-original-scan`. For a legacy plaintext scan (all six
in production on 2026-11-14), `remove-original-scan` only.

## Operator step and the production count

SQL sees the database, not the object store, so the query lists candidates
and the dry run decides. The **list query lives in the how-to**
(`docs/how-to/deleting-documents.md`, "Original scans of deleted documents"),
not here: this file moves on archive. It runs inside `BEGIN TRANSACTION READ
ONLY; … ROLLBACK;`.

The count for #454 is the how-to's query with its final `SELECT` replaced by:

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
BEGIN TRANSACTION READ ONLY;
SELECT count(*) FROM audit_records
WHERE step = 'ocr' AND to_state = 'extractable'
  AND NOT payload ? 'old_object_key';
ROLLBACK;
```

Result on 2026-11-14: 6 / 0 / 6 / 0, sanity 0 (see "Where the scan lives
today").

Reading the result:

- `key_row_still_present`: sealed scans of documents deleted before
  `originals-crypto-shred`; the rerun destroys the key and removes the scan.
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
  not its `object_key`. Issue #473 (default: include the scan in
  `originals-encrypt-existing` when that is built). Production has 0 live
  recovered documents on 2026-11-14.
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
  bytes, and leaves today's copy- and re-ingest-deletion behaviour in place.
- **Widening `doomed` without `lock_members`**: brings back the #462
  deadlock (see "Locks").
