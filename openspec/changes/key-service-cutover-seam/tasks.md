# Tasks

Nothing here touches the switch or the drop.

## 1. The seam

- [ ] The shared interface is pseudonymise, open an original, delete a
      document; `KeyProvider` and `MappingStore` are not it. Proved by: a test
      that the service driver implements it and exposes no method returning
      key material or ciphertext.
- [ ] The in-process driver implements it on `Pseudonymizer`,
      `DurableKeyProvider` and `PostgresMappingStore`; the service driver as
      calls to `/v1/...`. Proved by: the contract tests (below).
- [ ] The interface states its transaction contract: each operation atomic on
      its own; in-process takes part in the caller's transaction, the service
      driver commits in its own. Proved by: contract tests that roll the
      caller back after an operation, asserting the effect is gone in-process
      and stays through the service driver.
- [ ] Drivers selectable by configuration, in-process the default. Proved by:
      a test that unset configuration builds the in-process driver, and that
      an unknown value refuses to start.
- [ ] Contract tests against the interface run against both drivers. Proved
      by: one test module parametrised over both drivers, same results.
- [ ] Reveal is not in the interface and its routes are unchanged. Proved by:
      `test_reveal_authorize_first.py` unchanged and green.
- [ ] Pin: tokens are stable only while the vault moves intact. Proved by: a
      test that pseudonymises in-process, copies the vault into the service's
      database as a fixture and gets the same token through the service, and
      with one key's material changed gets a different token.

## 2. Maintenance mode

- [ ] The mode is a runtime switch in shared state, not an env flag. Proved
      by: a test with two app instances on one database where switching on
      makes both refuse writes with no restart, and switching off restores
      them.
- [ ] While maintenance is on, ingest and grant/role changes are refused with
      a retryable answer that names maintenance; nothing is written. Proved
      by: a test per route that the refusal comes before any write and the
      state is unchanged.
- [ ] The refusal comes before the request body is read, as the `/ingest`
      read gate. Proved by: a test that an upload in maintenance is refused
      with its body unread, next to `tests/test_ingest_gate.py`, and
      `tests/test_route_inventory.py` extended so every paused route is
      declared.
- [ ] Search, the console and reveal keep working in maintenance. Proved by:
      a test of each.
- [ ] Off by default. Proved by: a test that a fresh database accepts writes.
- [ ] Entering and leaving maintenance is recorded in the audit trail
      (append-only; no value in it). Proved by: a test reading the records.

## 3. The parent's duplicate requirements

- [ ] Remove the two seam requirements ("Both kinds of driver implement one
      interface of operations", "Tokens are stable only while the key vault
      moves intact") from `openspec/changes/key-service-cutover/specs/key-service/spec.md`
      (lines 20-54), keeping the other requirements. Proved by:
      `openspec validate key-service-cutover --strict` passes, and a grep
      finds each of the two requirement headings in exactly one change.

## 4. Roadmap (`docs/reference/roadmap.yml`)

- [ ] Parts 2a, 2b, 2c, 2d and 3 become `done` with the merged build PRs as
      evidence (#543, #549, #552, #555, #558; archives #545, #551, #554, #557,
      #560), replacing the stale 2a text about the stopped build (#541). "In
      production" is written only where a deploy is evidenced. Proved by: the
      file parses as YAML, every `done` item has an evidence link, and
      `git log` shows each PR merged.
- [ ] The item "wordsworth cut over to the key service, verified" stays open
      and names the three builds (seam, switch, drop) with this change as
      evidence for the seam. Proved by: the same YAML check.

## 5. The architect's other findings on #564

- [ ] Fold each remaining finding of the architect's comment on #564 in as a
      task here with its proof, before the build starts (open question in
      `proposal.md`). Proved by: every finding in the comment maps to a task
      in this file.

## 6. Docs (code without docs fails CI)

- [ ] `docs/how-to/key-service.md`: driver selection (in-process default,
      unknown refuses), the transaction difference between the drivers, and
      maintenance mode (what pauses, what stays up, how a script switches it).
- [ ] `docs/reference/architecture.md`: the seam (operations, why not
      `KeyProvider` / `MappingStore`, the transaction contract).
- [ ] `docs/reference/ingest.md` and `docs/how-to/grants.md`: the refusal in
      maintenance, before the body is read.
- [ ] `docs/reference/cli.md`: the command that switches maintenance, if the
      switch is a command (the default in `proposal.md`).
