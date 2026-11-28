# Tasks

Three builds in order (see `proposal.md`): seam, then switch, then drop. Each
gets its own change when its turn comes; the tasks below are its checklist.
Reveal is in none of them.

## 1. `key-service-cutover-seam`

- [ ] The shared interface is the operations of `design.md` ("The seam"), not
      `KeyProvider` / `MappingStore`. Proved by: a test that the service driver
      implements it and exposes no method returning key material or ciphertext.
- [ ] Drivers selectable by configuration (in-process / service), the in-process
      driver the default. Proved by: a test that an unset configuration builds
      the in-process driver, and that an unknown value refuses to start.
- [ ] Contract tests written against the shared interface run against both
      drivers and give the same results. Proved by: the same test module
      parametrised over both drivers.
- [ ] Pin: tokens stay stable only while the key vault moves intact. Proved by:
      a test that pseudonymises a value in-process, copies the vault into the
      service's database and pseudonymises it through the service (same token),
      and the same with one key's material changed (different token).
- [ ] Docs: `docs/how-to/key-service.md` (driver selection),
      `docs/reference/architecture.md` (the seam).

## 2. `key-service-cutover-switch`

- [ ] Pseudonymise, originals, open-limits and delete go to the service with
      the service driver; the old drivers stay in the code and the old tables
      stay. Proved by: the contract tests from the seam, plus a test per route.
- [ ] The migration copies and verifies (counts, decryptions equal, sample
      reveals equal, originals open) and aborts on any mismatch, leaving the
      old drivers active. Proved by: tests including an injected mismatch.
- [ ] The registry and every document's domain are copied and verified (row
      counts per provenance, `copied_minted` / `copied_backfilled`; each
      document's domain equals its `register` record; every token in every
      live document's current text is in the copied registry). Proved by:
      tests, including an injected mismatch and a missing registry row, each
      aborting the cutover.
- [ ] With the service driver wordsworth builds no key provider, Transit client
      or OpenBao credential for pseudonymise, originals, open-limits or
      delete, and no route of the service returns a clear value to the service
      credential. Proved by: tests. Reveal's in-process driver is excepted
      until it is switched.
- [ ] Reveal is untouched: the reveal routes, their driver and the reveal-api
      requirement are the same before and after. Proved by: the existing
      `test_reveal_authorize_first.py` unchanged and green, and a test that the
      reveal driver is the in-process one whatever the other drivers are.
- [ ] Rollback (drivers back to in-process) works inside the window. Proved by:
      a test.
- [ ] No clear value or key in logs or reports during migration. Proved by: a
      log-capture test.
- [ ] The box map no longer needs a decrypting route
      (`pdf_redaction._clear_values`). Proved by: a test with the service
      driver that builds the box map without any call returning a clear value.
- [ ] The service's management endpoints for roles, group mappings and grants,
      called by wordsworth's grant and role routes and the console. Proved by:
      tests per endpoint and per caller.
- [ ] Docs: `docs/how-to/key-service.md` (cutover, verification window,
      rollback), `docs/reference/key-service-api.md` (management endpoints),
      `docs/reference/architecture.md`, `docs/how-to/deleting-documents.md`,
      `docs/how-to/originals-encryption.md` and `docs/how-to/pdf-redaction.md`
      (the box map), `docs/reference/cli.md` (the migration command).

## 3. `key-service-cutover-drop`

Needs Mark's go-ahead (open question in `proposal.md`) and reveal switched.

- [ ] A separate command drops the old tables; it refuses inside the
      verification window. Proved by: a test of the refusal and of the drop
      after the window.
- [ ] After the drop, wordsworth's database user can't read any key, mapping or
      grant table (they are gone or revoked). Proved by: a test after the drop
      command.
- [ ] Docs: `docs/reference/cli.md` (the command and its window),
      `docs/how-to/key-service.md` (the point of no return).

## Alongside the seam (no code)

- [ ] Check whether the console's Keycloak session can forward a raw assertion
      to the key service, as reveal needs one. Proved by: a written result
      (yes/no, how) in the reveal change's proposal or an issue linked from
      `proposal.md`. It feeds Mark's answer on #524; it builds nothing.
