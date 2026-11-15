# Tasks

- [x] `--dry-run` reports what would be sealed and changes nothing. Proved by:
      a test comparing the store before and after.
- [x] Sealing verifies before removing plaintext: a sealed copy that doesn't
      open to the recorded hash leaves the plaintext in place. Proved by: a
      test with a corrupting store.
- [x] Idempotent and resumable. Proved by: a test running twice, and one
      interrupted halfway.
- [x] Before/after counts and bytes in the report; no document text, names or
      values in it. Proved by: a test on the report.
- [x] After a run, no live document has a legacy plaintext original. Proved by:
      a test, and a `--verify` mode for the live run.
- [x] The original scan of a live OCR-recovered document (`old_object_key` in
      its recovering `ocr` record, read through `deletion_scans.scan_keys`) is
      sealed by the same run when it is still plaintext, counted as `scans`
      (#473). Proved by: a test with a recovered document whose scan is
      plaintext, and one whose scan is already sealed.
- [x] A live recovered document's scan that is no longer in the store is
      skipped, not failed (reviewer finding on build #481, blocking):
      `candidates()` in `originals_seal.py` adds every `old_object_key` from
      `deletion_scans.scan_keys` without checking existence, and `seal_one()`
      turns the `ObjectStoreError` on read into a failure. Check
      `store.exists` for scan candidates and treat an `ObjectStoreError` on
      read of a scan as absent; report the status `gone`, counted as neither
      sealed nor failed, and keep the exit status clean. Proved by: a test for
      "already sealed OR no longer in the store → nothing done, nothing
      failed", with a recovered document whose scan is missing from the store
      (and one where reading raises `ObjectStoreError`), asserting status
      `gone`, `failed == 0` and `sealed` unchanged.
      (Done as: `seal_one` reads the scan under its row lock and reports
      `gone` on an `ObjectStoreError`, which covers both; tests
      `test_scan_no_longer_in_the_store_is_gone[deleted|unreadable]` and
      `test_scan_already_sealed_is_left_alone` in
      `tests/test_seal_originals_scans.py`.)
- [x] Docs: `docs/how-to/originals-encryption.md` (the migration, the dry run,
      verification, what to do on a failed document; the `gone` status for a
      scan that is no longer in the store, and that it is not a failure).
