# Tasks

- [ ] Drivers selectable by configuration (in-process / service), both tested
      against the same contract tests. Proved by: tests.
- [ ] The migration copies and verifies (counts, decryptions equal, sample
      reveals equal, originals open) and aborts on any mismatch, leaving the
      old drivers active. Proved by: tests including an injected mismatch.
- [ ] After cutover, wordsworth's database user can't read any key, mapping or
      grant table (they are gone or revoked). Proved by: a test after the
      drop command; the drop refuses inside the verification window.
- [ ] The registry and every document's domain are copied and verified (row
      counts per provenance, `copied_minted` / `copied_backfilled`; each
      document's domain equals its `register` record; every token in every
      live document's current text is in the copied registry). Proved by:
      tests, including an injected mismatch and a missing registry row, each
      aborting the cutover.
- [ ] wordsworth holds no key material with the service drivers: no key
      provider, Transit client or OpenBao credential is built, and no route
      of the service returns a clear value to the service credential. Proved
      by: tests.
- [ ] wordsworth's reveal routes with the service driver follow
      `key-service-reveal` ("Order on wordsworth's side"): no document row is
      read before `decide` answers; every service refusal maps to the same
      403 body; an outage is 503 with no fallback. Proved by: the existing
      `test_reveal_authorize_first.py` scenarios run against the service
      driver, plus a statement-count test on wordsworth's side.
- [ ] Rollback (drivers back to in-process) works inside the window. Proved by:
      a test.
- [ ] No clear value or key in logs or reports during migration. Proved by: a
      log-capture test.
- [ ] Docs: `docs/how-to/key-service.md` (cutover, verification window,
      rollback), `docs/reference/architecture.md`.
