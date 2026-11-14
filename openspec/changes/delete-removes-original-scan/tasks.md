# Tasks

Tests go in `tests/test_delete_scan_*.py` unless named otherwise; reuse
`tests/shred_setup.py` for sealed documents and `recover` with a fake
`OcrEngine` (as `test_ocr_sealed.py`) to make a recovered document. Every test
that needs a scan builds it through `recover`, not by writing an `ocr` record
by hand, except the legacy and old-deletion setups that cannot be reached
otherwise. In the tasks, A is a recovered document with scan S, C a
superseded copy whose `object_key` is S, N a later ingest of S's bytes.

## 1. The claim and the key candidates
- [ ] `deletion_scans.scan_keys(session, document_ids)`: the distinct
      `old_object_key` of the documents' recovering `ocr` records
      (`to_state = 'extractable'`). The one helper `doomed`, `lock_members`
      and the scan removal use.
- [ ] `deletion_keys._object_claimed_elsewhere` also counts a document that is
      not deleted and whose recovering `ocr` record names the object key as
      `old_object_key`. Proved by: deleting C while A is live leaves S and its
      key row, and C's `deleted` record has `object: 0`, `keys_destroyed: 0`.
- [ ] Second behaviour change. Proved by: N (live, `object_key` S, S's key row
      moved to N by `put_original`) deleted while A is live: S and its key row
      stay, N's record has `object: 0`, `keys_destroyed: 0`.
- [ ] `deletion_keys._candidate_rows` adds `object_key IN scan_keys`. Proved
      by: the sequence A recovered, N ingested (key row moves to N), N deleted
      (S and key stay), A deleted: after the last step S and its key row are
      both gone. Check that this test **fails** without the new clause.

## 2. Locks
- [ ] `doomed` adds the document's scan keys to its candidate object keys and
      locks, in its one ordered `FOR NO KEY UPDATE` statement, also the rows
      of documents whose recovering `ocr` record names a key in candidates ∪
      {former_key} ∪ scan_keys. Proved by: a test with two sessions: the first
      runs `doomed` for C and does not commit; the second, with a short
      `lock_timeout`, fails to run `doomed` for A; and a real concurrent
      deletion of A and C in two threads, once with S sealed and once with S
      legacy plaintext, after which neither S nor its key row exists. Check
      that the plaintext threaded test **fails** without the widened lock.
- [ ] `dossier_locks.lock_members` locks the same widened set up front:
      `_object_keys` adds `scan_keys` of the members, and the statement adds
      rows with a recovering `ocr` record naming a key in the set. Docstring
      updated. Proved by:
      - `tests/test_dossier_deletion_lock_set.py`: a dossier with recovered
        member A and copy C (outside the dossier) on S: while the dossier
        deletion holds its locks, `_try_lock` on C fails; a dry run locks
        nothing.
      - `tests/test_dossier_deletion_deadlocks.py`: the dossier holding A (and
        a second member with a lower id that is deleted first) and a
        concurrent deletion of C, C with a lower id than A: no
        `DeadlockDetected`, and after both S and its key are gone. Check that
        it **fails** with `doomed` widened and `lock_members` not.
- [ ] The audit-append deadlock tests of `originals-crypto-shred`
      (`test_shred_locks.py`) and the existing #462 tests still pass.

## 3. The scan
- [ ] New module `deletion_scans.py`: `scan_keys`, `plan(session,
      document_id, former_key, store)` (the scans that exist and no other
      document claims) and `record_rerun(...)`. `deletion.py` stays at or
      under 200 lines and calls it in one place, right after the object
      removal.
- [ ] `DeletionCounts` gains `original_scan`, after `object` in `as_dict()`.
      Proved by: deleting A with a sealed scan: both objects are gone, both
      key rows are gone, the record has `object: 1`, `original_scan: 1`,
      `keys_destroyed: 2`, and no object key, filename or key material in the
      payload.
- [ ] A legacy plaintext scan is removed. Proved by: A whose scan was written
      with a plain `put` and has no key row: after the deletion the scan is
      gone, `original_scan: 1`, `keys_destroyed` is 1 (the sealed OCR'd PDF).
- [ ] A scan no longer in the store counts 0 and does not fail. Proved by: a
      test that removes S from the store before the deletion.
- [ ] C still pointing at S keeps it. Proved by: delete A first (S and its
      key stay, `original_scan: 0`), then C (S and its key go, C has
      `object: 1`, `keys_destroyed: 1`).
- [ ] A live N keeps S. Proved by: deleting A while N is live leaves S and its
      key row.
- [ ] A failure removing the scan is a hard error. Proved by: a store whose
      `delete` raises for S: the call raises, no `deleted` record, and a rerun
      with a healthy store completes the deletion and removes S.
- [ ] The dry run counts and removes nothing. Proved by: `wordsworth-delete
      --dry-run` on A prints `original_scan: 1`; S and its key row still
      exist; no record.

## 4. Reruns
- [ ] A rerun over an already-deleted document that removes a scan appends
      one `deleted` → `deleted` record, step `remove-original-scan`, payload
      `{actor, original_scan}`. Proved by: deleting A with the scan step
      patched out (simulating a deletion from before this change, key already
      destroyed), then deleting again (S gone, one `remove-original-scan`
      record, no `destroy-key` record, `audit.verify_chain` passes), then a
      third time (no record).
- [ ] Each leftover keeps its own record. Proved by: a deleted A with S still
      stored, S's key row put back by hand (as `test_shred_records.py` does)
      and one cached render: the rerun appends exactly one
      `remove-original-scan`, one `destroy-key` and one `remove-renders`, each
      payload with only its own counts, and the chain verifies.
- [ ] The dry run over an old deletion reports `original_scan: 1` and
      appends nothing.

## 5. Callers and reports
- [ ] API delete, `wordsworth-delete` with a plain object store, and dossier
      delete each remove the scan. Proved by: one test per path.
- [ ] `DossierDeletionReport.original_scan` is the sum over deleted members,
      in `as_dict()`, the `DELETE /dossiers/{id}` answer and
      `wordsworth-delete --dossier` output, real and dry run; a released
      member keeps its scan. Proved by: a dossier with one exclusive and one
      shared recovered document.
- [ ] Existing tests that assert a whole counts dictionary or payload gain
      `original_scan: 0` (`test_delete_documents.py`, `test_delete_cli.py`,
      `test_delete_dossiers.py`, `test_shred_*.py`); nothing else in them
      changes.

## 6. Docs
- [ ] `docs/how-to/deleting-documents.md`:
      - the scan in "What goes, what stays";
      - `original_scan` in the counts and the dossier sums;
      - the claim (a recovered document claims its scan; the two behaviour
        changes) under "The key follows the object";
      - the scan in the paragraph on partial failures (the rerun gap);
      - in "Original scans of deleted documents", drop the "after … is
        deployed" markers and the "today" note in the crypto-shredding
        section.
- [ ] `docs/reference/cli.md`: `original_scan` in the `wordsworth-delete`
      output.
- [ ] `docs/reference/architecture.md` (deletion) if it lists what a deletion
      removes.
- [ ] `uv run ruff check src/ tests/` and the full suite against a private
      test database; report which tests skipped.
