# Tasks

## 1. The key store
- [x] `DocumentKeys.evict(object_keys)` drops those entries from the unwrap
      cache and touches nothing else. Proved by: a unit test: after `evict`,
      the next `unwrap` of a key whose row still exists goes through the key
      service again (counted by a wrapper around `FakeTransit` that counts
      `unwrap` calls, defined in the test file; `FakeTransit` itself does not
      count).
- [x] `unwrap` reads the key row from the database on the hit path and on the
      miss path, and trusts a cached key only while a row with the same
      `key_id` exists. Proved by: a test with two `DocumentKeys` instances on
      one database (two replicas): the second unwraps and so caches the key,
      the first session deletes the row and commits, the second's `unwrap`
      raises `OriginalsKeyUnavailable` within the TTL, with no further call on
      the counting wrapper.
- [x] The miss path does not answer from the identity map. Proved by: a test
      where one session loads the key row, another session deletes it and
      commits, the cache is empty, and `unwrap` on the first session raises
      `OriginalsKeyUnavailable` without a call on the counting wrapper.
- [x] A key destroyed and minted again under the same object key is not served
      from the old cache entry. Proved by: the two-instance test, with a
      `mint` after the row is deleted: the second instance returns the new
      key.
- [x] The engine runs READ COMMITTED. Proved by: a test that reads
      `SHOW transaction_isolation` on a session from `make_session_factory`.

## 2. Deletion
- [x] `deletion_keys.destroy(session, object_keys)` deletes the rows with SQL
      and `delete_document` calls it for the keys `deletion_keys.doomed`
      names, after the object removal and before the audit record; `keys` is
      optional and only evicted. Proved by: a test that after deleting with
      `keys=None`, the document's key row is gone and a copy of the sealed
      object taken BEFORE the deletion can no longer be opened (simulating a
      backup); and one with `keys` given, asserting its cache no longer holds
      the entry.
- [x] `doomed` runs before the index entry and the object are removed. Proved
      by: a test with a `doomed` that raises: the index entry and the object
      still exist.
- [x] An OCR-recovered document loses both keys. Proved by: a test with a
      document that has a scan and an OCR'd PDF: both rows are gone and
      `keys_destroyed` is 2.
- [x] Deleting a superseded copy never destroys the survivor's key. Proved by:
      a test with a copy and a survivor on one object key, once with the key
      row carrying the survivor's id and once the copy's: after deleting the
      copy the row exists and the survivor's original opens.
- [x] A deleted document whose object is kept for another row keeps the key
      until that row is deleted too. Proved by: the same pair, deleting the
      survivor first (key and object stay, `keys_destroyed` is 0), then the
      copy (both go, `keys_destroyed` is 1).
- [x] Two deletions of a copy and its survivor at once leave neither the
      object nor the key. Proved by: a test with two sessions: the first runs
      `doomed` for the copy and does not commit; the second, with a short
      `lock_timeout`, fails to get the lock while the first is open; after the
      first commits, the second deletion runs and the object and the key row
      are gone.
- [x] A failure destroying the key leaves the document undeleted (hard error,
      no `deleted` record), and a rerun finishes. Proved by: a test with a
      `deletion_keys.destroy` patched to raise, then unpatched.
- [x] A legacy plaintext original deletes as before. Proved by: a test with a
      document without a key row: deleted, `keys_destroyed` is 0.
- [x] The `deleted` record carries `keys_destroyed` and no key material.
      Proved by: a test on the audit payload, asserting neither the wrapped
      nor the clear key bytes occur in it.
- [x] Deleting an already-deleted document that still has a key row destroys
      it and appends one `deleted` → `deleted` record with step `destroy-key`
      and `{actor, keys_destroyed}`; a rerun with nothing to destroy appends
      nothing. Proved by: a test that deletes a document, puts a key row back
      for it by hand, deletes again (one new record, row gone, hash chain
      verifies) and a third time (no new record).

## 3. Callers and reports
- [x] `api.py` passes its `DocumentKeys`; `delete_cli.py` passes none and
      still shreds; `dossier_deletion.delete_dossier` passes on an optional
      `keys`. Proved by: one test per path (API delete, `wordsworth-delete`
      with a plain object store, dossier delete) asserting the key row is
      gone.
- [x] `DossierDeletionReport.keys_destroyed` is the sum over the documents the
      dossier deletion deleted, in `as_dict()`, in the answer of
      `DELETE /dossiers/{id}` and in the output of `wordsworth-delete
      --dossier`. Proved by: a test with a dossier of two sealed documents and
      one shared with another dossier: the sum is 2, in all three places.
- [x] Dry run reports `keys_destroyed` and changes nothing, for a document and
      for a dossier. Proved by: a test for each that the count equals what the
      real run then destroys and that the rows exist after the dry run.
- [x] The existing calls of `delete_document` in the tests still pass: 12 in
      `tests/test_delete_documents.py`, 3 in `tests/test_console.py` (109,
      159, 205). Proved by: the suite, and `git diff` showing those files
      changed only where an expectation lists every count.

## 4. Docs
- [x] `docs/how-to/deleting-documents.md`: crypto-shredding; that the key
      follows the object (superseded copies); that it holds on every replica
      at once and relies on READ COMMITTED; the limits of proposal.md
      (database backups and their retention; requests in flight); documents
      deleted before this change, with the query that lists them and the
      instruction to run `wordsworth-delete` on them again, which records
      `destroy-key`. `docs/reference/cli.md`: `keys_destroyed` in the output
      for a document and for a dossier, dry run and real. Proved by: `grep -n
      "keys_destroyed" docs/how-to/deleting-documents.md
      docs/reference/cli.md` finds both, and `grep -n "destroy-key"
      docs/how-to/deleting-documents.md` finds the rerun.

## 5. Check
- [x] `deletion.py`, `deletion_keys.py` and `document_keys.py` are under 200
      lines; `dossier_deletion.py` does not grow beyond the sum and the
      parameter. Proved by: `wc -l` and `git diff --stat`.
- [x] `openspec validate originals-crypto-shred --strict` passes.
- [x] `uv run ruff check src/ tests/` is clean, the full suite passes and
      `/security-review` is clean. Proved by: the output in the PR, with the
      skipped tests listed.
