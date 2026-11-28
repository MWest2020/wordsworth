# Design

## Choices

- **A separate command, not a step of the migration.** The migration and the
  switch are reversible by configuration; the drop is not. Keeping it apart
  means nobody drops tables by running the cutover.
- **The window is enforced by the command.** It refuses inside the window
  (configurable, default 7 days) and says how long is left. The window is
  measured from the moment the switch completed, which the switch change
  records; where it records it is that change's to fix.
- **Last of three builds.** Order: seam, switch, drop (see
  `key-service-cutover`, "Three builds").
- **Gated by a person.** Mark's go-ahead comes before the build and before the
  run. Waiting for the window alone is not enough.

## Rejected alternatives

- **Dropping at the end of the migration.** Rollback to the in-process drivers
  would be impossible.
- **A timer that drops once the window passes.** A destructive action nobody
  decided on the day.
- **A flag that overrides the window.** The window is the safety; an override
  is a way round it.

## Not decided

Table names, drop versus revoke, and where the switch time is stored: see the
open questions in `proposal.md`. Nothing here is a requirement for them.
