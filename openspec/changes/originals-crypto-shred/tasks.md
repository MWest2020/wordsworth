# Tasks

- [ ] Deletion destroys the document's data key. Proved by: a test that after
      deleting, a copy of the object taken BEFORE deletion can no longer be
      opened (simulating a backup).
- [ ] A key shared by a live duplicate survives; it is destroyed when the last
      document using it is deleted. Proved by: a two-document test.
- [ ] A failure destroying the key leaves the document undeleted (hard error,
      no `deleted` record). Proved by: a test with a key store that raises.
- [ ] Dry run reports `keys_destroyed`/`keys_kept` and changes nothing. Proved
      by: a test.
- [ ] Docs: `docs/how-to/deleting-documents.md` (crypto-shredding, shared keys,
      backups).
