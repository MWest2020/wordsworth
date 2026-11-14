# Tasks

- [ ] `--dry-run` reports what would be sealed and changes nothing. Proved by:
      a test comparing the store before and after.
- [ ] Sealing verifies before removing plaintext: a sealed copy that doesn't
      open to the recorded hash leaves the plaintext in place. Proved by: a
      test with a corrupting store.
- [ ] Idempotent and resumable. Proved by: a test running twice, and one
      interrupted halfway.
- [ ] Before/after counts and bytes in the report; no document text, names or
      values in it. Proved by: a test on the report.
- [ ] After a run, no live document has a legacy plaintext original. Proved by:
      a test, and a `--verify` mode for the live run.
- [ ] The original scan of a live OCR-recovered document (`old_object_key` in
      its recovering `ocr` record, read through `deletion_scans.scan_keys`) is
      sealed by the same run when it is still plaintext, counted as `scans`
      (#473). Proved by: a test with a recovered document whose scan is
      plaintext, and one whose scan is already sealed.
- [ ] Docs: `docs/how-to/originals-encryption.md` (the migration, the dry run,
      verification, what to do on a failed document).
