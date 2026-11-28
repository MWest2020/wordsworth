# Tasks

Nothing here touches the switch or the drop.

## 1. The seam

- [ ] The shared interface is pseudonymise, open an original, delete a
      document; `KeyProvider` and `MappingStore` are not it. Proved by: a test
      that the service driver implements it and exposes no method returning
      key material or ciphertext.
- [ ] The in-process driver implements it on `Pseudonymizer`,
      `DurableKeyProvider` and `PostgresMappingStore`; the service driver as
      calls to `/v1/...`. Proved by: the contract tests (next task).
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

- [ ] While maintenance is on, ingest and grant/role changes are refused with
      a retryable answer that names maintenance; nothing is written. Proved
      by: a test per route that the refusal comes before any write and the
      state is unchanged.
- [ ] Search, the console and reveal keep working in maintenance. Proved by:
      a test of each.
- [ ] Off by default; turning it off restores the writes. Proved by: a test
      that an unset configuration accepts writes, and a switch on then off.
- [ ] Entering and leaving maintenance is recorded in the audit trail
      (append-only; no value in it). Proved by: a test reading the records.

## 3. Roadmap (`docs/reference/roadmap.yml`)

- [ ] Parts 2a, 2b, 2c, 2d and 3 become `done` with the merged build PRs as
      evidence (#543, #549, #552, #555, #558; archives #545, #551, #554, #557,
      #560), replacing the stale 2a text about the stopped build (#541). "In
      production" is written only where a deploy is evidenced. Proved by: the
      file parses as YAML, every `done` item has an evidence link, and
      `git log` shows each PR merged.
- [ ] The item "wordsworth cut over to the key service, verified" stays open
      and names the three builds (seam, switch, drop) with this change as
      evidence for the seam. Proved by: the same YAML check.

## 4. Docs (code without docs fails CI)

- [ ] `docs/how-to/key-service.md`: driver selection (in-process default,
      unknown refuses) and maintenance mode (what pauses, what stays up, how
      to switch it).
- [ ] `docs/reference/architecture.md`: the seam (operations, why not
      `KeyProvider` / `MappingStore`).
- [ ] `docs/reference/ingest.md` and `docs/how-to/grants.md`: the refusal in
      maintenance.
- [ ] `docs/reference/cli.md`: only if maintenance mode is switched by a
      command (open question in `proposal.md`).
