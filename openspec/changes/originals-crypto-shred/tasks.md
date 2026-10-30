# Tasks

- [ ] Deletion destroys the document's data key. Proved by: a test that after
      deleting, the document's key is gone and a copy of the object taken
      BEFORE deletion can no longer be opened (simulating a backup).
- [ ] A failure destroying the key leaves the document undeleted (hard error,
      no `deleted` record). Proved by: a test with a key store that raises.
- [ ] Dry run reports `keys_destroyed` and changes nothing. Proved by: a test.
- [ ] Docs: `docs/how-to/deleting-documents.md` (crypto-shredding, backups) and
      `docs/reference/cli.md` (dry-run output). Proved by:
      `grep -n "keys_destroyed" docs/how-to/deleting-documents.md
      docs/reference/cli.md` finds both.
