# Tasks

Tests go in `tests/test_delete_scan_*.py`; reuse `tests/shred_setup.py` for
sealed documents and `recover` with a fake `OcrEngine` (as `test_ocr_sealed.py`)
to make a recovered document. Every test that needs a scan builds it through
`recover`, not by writing an `ocr` record by hand, except the legacy and
old-deletion setups that cannot be reached otherwise.

## 1. The claim
- [ ] `deletion_keys._object_claimed_elsewhere` also counts a document that is
      not deleted and whose recovering `ocr` record (`to_state =
      'extractable'`) names the object key as `old_object_key`. Proved by: a
      test with a recovered survivor A (scan S) and a superseded copy C whose
      `object_key` is S: deleting C while A is live leaves S and its key row,
      and C's `deleted` record has `object: 0`, `keys_destroyed: 0`.
- [ ] `doomed` adds the document's scan keys to its candidate object keys and
      locks, in its one ordered `FOR NO KEY UPDATE` statement, also the rows
      of documents whose `ocr` record names a candidate. Proved by: a test with
      two sessions: the first runs `doomed` for C and does not commit; the
      second, with a short `lock_timeout`, fails to run `doomed` for A; and a
      real concurrent deletion of A and C in two threads after which neither S
      nor its key row exists. Check that the threaded test **fails** without
      the widened lock.
- [ ] The audit-append deadlock test of `originals-crypto-shred`
      (`test_shred_locks.py`) still passes with the widened lock.

## 2. The scan
- [ ] New module `deletion_scans.py`: `scan_keys(session, document_id)`
      (distinct `old_object_key` of the document's recovering `ocr` records,
      minus the former key), `plan(session, document_id, former_key, store)`
      (the scans that exist and no other document claims) and
      `record_rerun(...)`. `deletion.py` stays at or under 200 lines and calls
      it in one place, right after the object removal.
- [ ] `DeletionCounts` gains `original_scan`, after `object` in `as_dict()`.
      Proved by: a test that deletes a recovered document with a sealed scan:
      both objects are gone, both key rows are gone, the record has
      `object: 1`, `original_scan: 1`, `keys_destroyed: 2`, and no object key,
      filename or key material in the payload.
- [ ] A legacy plaintext scan is removed. Proved by: a recovered document
      whose scan was written with a plain `put` and has no key row: after the
      deletion the scan is gone, `original_scan: 1`, `keys_destroyed` is 1 (the
      sealed OCR'd PDF).
- [ ] A scan no longer in the store counts 0 and does not fail. Proved by: a
      test that removes S from the store before the deletion.
- [ ] A superseded copy still pointing at S keeps it. Proved by: delete A
      first (S and its key stay, `original_scan: 0`), then C (S and its key
      go, C has `object: 1`, `keys_destroyed: 1`).
- [ ] A re-ingest of the scan's bytes keeps it. Proved by: a test where a
      live document N has `object_key` S; deleting A leaves S and its key row.
- [ ] A failure removing the scan is a hard error. Proved by: a store whose
      `delete` raises for S: the call raises, no `deleted` record, and a rerun
      with a healthy store completes the deletion and removes S.
- [ ] The dry run counts and removes nothing. Proved by: `wordsworth-delete
      --dry-run` on A prints `original_scan: 1`; S and its key row still
      exist; no record.

## 3. Reruns
- [ ] A rerun over an already-deleted document that removes a scan appends
      one `deleted` → `deleted` record, step `remove-original-scan`, payload
      `{actor, original_scan}`; nothing removed, nothing appended. Proved by:
      a test that deletes A with the scan step patched out (simulating a
      deletion from before this change, key already destroyed), then deletes
      again (S gone, one `remove-original-scan` record, no `destroy-key`
      record, `audit.verify_chain` passes), then a third time (no record).
- [ ] A rerun that also destroys a key and removes renders writes each its
      own record (`destroy-key`, `remove-renders`, `remove-original-scan`) in
      one transaction. Proved by: a test that puts the key row back by hand
      before the rerun, as `test_shred_records.py` does.
- [ ] The dry run over an old deletion reports `original_scan: 1` and
      appends nothing.

## 4. Callers and reports
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

## 5. Docs
- [ ] `docs/how-to/deleting-documents.md`: the scan in "What goes, what
      stays"; `original_scan` in the counts and the dossier sums; the claim
      rule (a recovered document claims its scan) under "The key follows the
      object"; the section "Removing original scans of documents deleted
      before this change" with the list query from design.md, the dry run,
      the rerun and the `remove-original-scan` record; remove the "until
      `delete-removes-original-scan` is deployed" note.
- [ ] `docs/reference/cli.md`: `original_scan` in the `wordsworth-delete`
      output.
- [ ] `docs/reference/architecture.md` (deletion) if it lists what a deletion
      removes.
- [ ] `uv run ruff check src/ tests/` and the full suite against a private
      test database; report which tests skipped.
