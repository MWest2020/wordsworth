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
- **A write-pause (maintenance mode)**: while on, ingest and grant/role
  changes are refused; search and the console stay up. The migration of the
  switch change runs inside it so the copied state is consistent. Only the
  mechanism is here; nothing calls it for a migration yet.
- **The roadmap fix** in `docs/reference/roadmap.yml`: see `tasks.md`.

## Not in this change

The switch of any operation to the service, the migration and its
verification, the management endpoints, the box-map change, reveal, and the
drop of the old tables.

## Open questions

- **Which writes the maintenance mode pauses beyond ingest and grant/role
  changes** (document deletion in particular), and how it is switched on (a
  setting or a command). Default: ingest and grant/role changes only, as in
  the plan; the build settles the rest and a requirement is added only once
  decided.
- **The parent change's duplicate deltas.** `key-service-cutover/specs/` still
  carries the seam requirements (one interface, token stability). When this
  change is applied they exist twice. Default: the parent's copies are
  removed when the switch change is proposed; this change is archived first.
- **Whether the key-service parts on the roadmap are deployed**, not only
  merged and archived. Default: the roadmap says merged and archived, and
  says "in production" only where a deploy is evidenced.

## Depends on

`key-service-skeleton`, `key-service-pseudonymise`, `key-service-originals`,
`key-service-open-limits`, `key-service-delete`, `key-service-reveal` (all
archived).
