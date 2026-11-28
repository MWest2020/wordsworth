# Tasks

Not started until `key-service-cutover-switch` is archived, its window has run
out, reveal is switched, and Mark has given his go-ahead (see `proposal.md`).

## 1. The drop command

- [ ] A separate command drops the old key, mapping and grant tables. Proved
      by: a test that runs it after the window and finds the tables gone.
- [ ] The command refuses inside the verification window (default 7 days,
      configurable). Proved by: a test of the refusal that leaves every table
      in place.
- [ ] After the drop, wordsworth's database user can read no key, mapping or
      grant table. Proved by: a test after the drop command that a read
      fails.
- [ ] The migration and the switch never drop anything. Proved by: a test that
      the migration command leaves the old tables in place.

## 2. Docs

- [ ] `docs/reference/cli.md`: the command and its window.
- [ ] `docs/how-to/key-service.md`: the point of no return, and that rollback is
      not possible after it.
