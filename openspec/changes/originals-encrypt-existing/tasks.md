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
- [ ] Docs: `docs/how-to/originals-encryption.md` (the migration, the dry run,
      verification, what to do on a failed document).
