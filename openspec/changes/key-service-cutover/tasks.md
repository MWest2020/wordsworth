# Tasks

- [ ] Drivers selectable by configuration (in-process / service), both tested
      against the same contract tests. Proved by: tests.
- [ ] The migration copies and verifies (counts, decryptions equal, sample
      reveals equal, originals open) and aborts on any mismatch, leaving the
      old drivers active. Proved by: tests including an injected mismatch.
- [ ] After cutover, wordsworth's database user can't read any key, mapping or
      grant table (they are gone or revoked). Proved by: a test after the
      drop command; the drop refuses inside the verification window.
- [ ] Rollback (drivers back to in-process) works inside the window. Proved by:
      a test.
- [ ] No clear value or key in logs or reports during migration. Proved by: a
      log-capture test.
- [ ] Docs: `docs/how-to/key-service.md` (cutover, verification window,
      rollback), `docs/reference/architecture.md`.
