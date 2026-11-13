# Tasks

## 1. The key store
- [ ] `DocumentKeys.destroy(session, object_keys) -> int` deletes the rows,
      evicts them from the cache and returns the number deleted; it calls no
      key service. Proved by: a unit test with a `FakeTransit` that counts
      calls: rows gone, return value right, no transit call, and a later
      `unwrap` raises `OriginalsKeyUnavailable`.
- [ ] `unwrap` trusts a cached key only while a row with the same `key_id`
      exists, checked with a query that reaches the database. Proved by: a
      test with two `DocumentKeys` instances on one database (two replicas):
      the second unwraps and so caches the key, the first destroys it and
      commits, the second's `unwrap` raises `OriginalsKeyUnavailable` within
      the TTL, without a transit call.
- [ ] A key destroyed and minted again under the same object key is not served
      from the old cache entry. Proved by: the same two-instance test, with a
      `mint` after the `destroy`: the second instance returns the new key.

## 2. Deletion
- [ ] `delete_document` takes `keys` and destroys the keys `deletion_keys.
      doomed` names, after the object removal and before the `deleted`
      transition. Proved by: a test that after deleting, the document's key
      row is gone and a copy of the sealed object taken BEFORE the deletion
      can no longer be opened (simulating a backup).
- [ ] An OCR-recovered document loses both keys. Proved by: a test with a
      document that has a scan and an OCR'd PDF: both rows are gone and
      `keys_destroyed` is 2.
- [ ] Deleting a superseded copy never destroys the survivor's key. Proved by:
      a test with a copy and a survivor on one object key, once with the key
      row carrying the survivor's id and once the copy's: after deleting the
      copy the row exists and the survivor's original opens.
- [ ] A deleted document whose object is kept for another row keeps the key
      until that row is deleted too. Proved by: the same pair, deleting the
      survivor first (key and object stay, `keys_destroyed` is 0), then the
      copy (both go, `keys_destroyed` is 1).
- [ ] A failure destroying the key leaves the document undeleted (hard error,
      no `deleted` record), and a rerun finishes. Proved by: a test with a key
      store whose `destroy` raises, then one that does not.
- [ ] `keys=None` with a key to destroy is an error, not a skipped step.
      Proved by: a test that the deletion raises and writes no `deleted`
      record.
- [ ] A legacy plaintext original deletes as before. Proved by: a test with a
      document without a key row: deleted, `keys_destroyed` is 0.
- [ ] The three callers pass the key store: `api.py`, `delete_cli.py`,
      `dossier_deletion.py`. Proved by: one test per path (API delete, CLI
      delete, dossier delete) asserting the key row is gone.
- [ ] The `deleted` record carries `keys_destroyed` and no key material.
      Proved by: a test on the audit payload, asserting neither the wrapped
      nor the clear key bytes occur in it.
- [ ] Dry run reports `keys_destroyed` and changes nothing, for a document and
      for a dossier. Proved by: a test for each that the count equals what the
      real run then destroys and that the rows exist after the dry run.

## 3. Docs
- [ ] `docs/how-to/deleting-documents.md`: crypto-shredding; that the key
      follows the object (superseded copies); that it holds on every replica
      at once; the limits of proposal.md (database backups and their
      retention, documents deleted before this change with the query that
      counts them, requests in flight). `docs/reference/cli.md`: the dry-run
      output. Proved by: `grep -n "keys_destroyed"
      docs/how-to/deleting-documents.md docs/reference/cli.md` finds both.

## 4. Check
- [ ] `deletion.py` and `deletion_keys.py` are under 200 lines, and
      `document_keys.py` stays under 200. Proved by: `wc -l`.
- [ ] `openspec validate originals-crypto-shred --strict` passes.
- [ ] `uv run ruff check src/ tests/` is clean, the full suite passes and
      `/security-review` is clean. Proved by: the output in the PR, with the
      skipped tests listed.
