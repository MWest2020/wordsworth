# key-service-cutover-seam

## Why

`key-service-cutover` was split after the architect failed it twice (#559,
#561): "the change is several builds in one and a builder would have to
guess". This is the first of the three builds, the seam only: the interface
both kinds of driver share, the choice of driver by configuration, the
maintenance mode a later migration needs, and a corrected roadmap. Nothing in
it touches the switch or the drop, and production behaviour does not change:
the in-process drivers stay the default.

The plan it belongs to is in `openspec/changes/key-service-cutover/`
(ADR-0009 migration step 2): seam, then `key-service-cutover-switch`, then
`key-service-cutover-drop`.

## What changes

- **The seam.** One interface of operations that wordsworth asks of a key
  authority: pseudonymise, open an original, delete a document. The in-process
  driver implements it on `Pseudonymizer`, `DurableKeyProvider` and
  `PostgresMappingStore`; a service driver implements it as calls to `/v1/...`.
  The service driver exposes no operation that returns key material or
  ciphertext. `KeyProvider` and `MappingStore` are not the shared interface.
  Reveal is not in it.
- **Driver selection by configuration**, the in-process driver the default; an
  unknown value refuses to start.
- **Contract tests** written against the interface and run against both
  drivers; they are the proof that the later switch changes no behaviour.
- **A pin test** that tokens stay the same only while the key vault moves
  intact (same key ids, material, scopes).
- **A transaction contract** on the interface: each operation is atomic on its
  own; the in-process driver takes part in the caller's transaction, the
  service driver commits in its own and does not roll back with the caller.
- **A write-pause (maintenance mode)**: while on, ingest and grant/role
  changes are refused before the body is read; search and the console stay
  up. It is a runtime switch in shared state, not an env flag, so the switch
  migration can turn it on from a script without restarting replicas. The
  migration of the switch change runs inside it so the copied state is
  consistent. Only the mechanism is here; nothing calls it for a migration yet.
- **The parent's copies of the seam requirements are removed**
  (`key-service-cutover/specs/key-service/spec.md:20-54`), so each requirement
  has one source.

This amends the change after the architect failed it on #564 (five gaps, each
checked against the code).
- **The roadmap fix** in `docs/reference/roadmap.yml`: see `tasks.md`.

## Not in this change

The switch of any operation to the service, the migration and its
verification, the management endpoints, the box-map change, reveal, and the
drop of the old tables.

## Open questions

- **Which writes the maintenance mode pauses beyond ingest and grant/role
  changes** (document deletion in particular). Default: ingest and grant/role
  changes only, as in the plan; a requirement is added only once decided.
- **Where the switch lives and how a script flips it.** Decided: a runtime
  switch in shared state. Open: the storage (the architecture says state is
  derived from the append-only audit trail, so the latest enter/leave audit
  record is a candidate; a small settings row is the other) and the interface
  (a command or an admin endpoint). Default: derived from the latest audit
  record, switched by a CLI command.
- **The architect's remaining gaps on #564.** The decision summary cut them
  off and the issue comment was not readable when this was amended. They are
  not turned into requirements here. Default: whoever builds reads the full
  comment on #564 and the findings are added to `tasks.md` before the build
  starts.
- **Ordering and compensation across the transaction difference**, e.g. what a
  caller does when its own write fails after a service operation committed.
  Default: not specified by the seam; the switch change settles it per
  operation.
- **Whether the key-service parts on the roadmap are deployed**, not only
  merged and archived. Default: the roadmap says merged and archived, and
  says "in production" only where a deploy is evidenced.

## Depends on

`key-service-skeleton`, `key-service-pseudonymise`, `key-service-originals`,
`key-service-open-limits`, `key-service-delete`, `key-service-reveal` (all
archived).
