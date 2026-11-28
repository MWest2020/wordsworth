# key-service-cutover-drop

## Why

Split from `key-service-cutover` (amended after the architect's FAIL on #559,
where the change was "several builds in one"): the drop only. It is the one
step of the cutover that cannot be undone, so it is its own change, last, and
gated.

Decided in the channel: "The old tables are dropped by a separate command, only
after a verification window that defaults to 7 days", and "the drop of the old
tables comes after the 7-day window and needs Mark's go-ahead when the time
comes."

## What changes

- A separate command drops the old key, mapping and grant tables from
  wordsworth's database. It refuses inside the verification window
  (configurable, default 7 days).
- After the drop, wordsworth's database user can read no key, mapping or grant
  table (gone or revoked).
- The docs for the command and the point of no return.

## Depends on

- `key-service-cutover-switch`, archived, and the verification window it opens
  having run out (default 7 days).
- Mark's go-ahead, before this change is built and before the command is run.
- Reveal switched to the service. `key-service-cutover` records that the
  in-process reveal needs the key vault and mappings, so the drop cannot run
  while reveal is in-process.

## Open questions

- **Mark's go-ahead (not given).** Default: this change is not built and the
  command is not run.
- **Reveal's switch (#524, Mark).** Whether reveal needs a signed identity and
  whether the console can forward one is undecided. Until reveal is switched
  this change cannot be applied. Default: not built.
- **Which tables exactly, and drop versus revoke.** The channel says "the old
  tables"; the names and the choice between dropping and revoking are not
  decided. They are fixed in the switch change, which knows what it copied.
- **`key-service-cutover` still carries the drop.** Its `specs/key-service`
  delta holds the scenario "After the window nothing sensitive is left behind"
  and its tasks section 3 holds the drop. Whether these move here when that
  change is amended or archived is not decided; this change names its own
  requirements differently so the two do not collide.
