# Tasks

Prerequisite: `key-service-cutover-seam` is archived.

- [ ] Pseudonymise, originals, open-limits and delete use the service driver
      when configured; old drivers and tables stay. Proved by: the seam's
      contract tests plus a test per route.
- [ ] The migration copies and verifies (counts, decryptions equal, originals
      open) and aborts on any mismatch, leaving the old drivers active. Proved
      by: tests including an injected mismatch.
- [ ] The registry and every document's domain are copied and verified (row
      counts per provenance, `copied_minted` / `copied_backfilled`; each
      document's domain equals its `register` record; every token in every live
      document's current text is in the copied registry). Proved by: tests,
      including an injected mismatch and a missing registry row, each aborting
      the cutover.
- [ ] With the service driver wordsworth builds no key provider, Transit client
      or OpenBao credential for the four switched operations, and no route
      returns a clear value to the service credential. Proved by: tests.
- [ ] Reveal is untouched. Proved by: `test_reveal_authorize_first.py`
      unchanged and green, and a test that the reveal driver is the in-process
      one whatever the other drivers are.
- [ ] Rollback to in-process works inside the window. Proved by: a test.
- [ ] No clear value or key in logs or reports during migration. Proved by: a
      log-capture test.
- [ ] The box map is built without a decrypting route. Proved by: a test with
      the service driver that builds it with no call returning a clear value.
- [ ] Management endpoints for roles, group mappings and grants, called by
      wordsworth's grant and role routes and the console. Proved by: tests per
      endpoint and per caller.
- [ ] Docs, in the same PR: `docs/how-to/key-service.md` (cutover, window,
      rollback), `docs/reference/key-service-api.md` (management endpoints),
      `docs/reference/architecture.md`, `docs/how-to/deleting-documents.md`,
      `docs/how-to/originals-encryption.md`, `docs/how-to/pdf-redaction.md`
      (the box map), `docs/reference/cli.md` (the migration command). Proved
      by: CI docs check.
