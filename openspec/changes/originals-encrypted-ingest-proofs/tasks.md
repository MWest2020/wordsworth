# Tasks

A skipped test counts as failed for every reviewer. Tests use `FakeTransit`
and the in-memory store. Depends on `originals-encrypted-ingest` being merged
and built.

- [ ] 0.1 Verify the ingest change is on main, else stop. Proved by:
      `git log main` shows the `originals-encrypted-ingest` build merged, and
      `mem_originals` exists in `tests/conftest.py` and a shared
      `transit_for` helper exists in `src/`. If not, do nothing further and
      report that the dependency is missing.
- [ ] 0.2 Migrate any test still on the old `store` signatures. Proved by:
      `grep -rn "store=" tests/` finds no caller of `process`, `reanonymize`,
      `recover`, `ingest` or `create_app`, and the suite passes with no skips
      added.

- [ ] 1.1 Register-first ordering. Proved by: a test with a spy store that the
      document row is flushed before `put_original` is called, and that the key
      row's `document_id` is the registered document's id.
- [ ] 1.2 Rollback on a failed ingest after a write. Proved by: a test where
      the dossier add fails after `PutResult.WROTE`: no object, no key row and
      no document remain; and a test where `put_original` did not write (the
      object already existed for a live document) and a later step fails: the
      existing object is still there.
- [ ] 2.1 Fail closed at the API. Proved by: two API tests (reversible and
      irreversible mode) with a Transit that raises: 503 with
      `key service unavailable`, and the store holds no object.
- [ ] 2.2 Batch stops at the first key failure. Proved by: an API test with a
      three-file batch whose transit fails on the second file: file 1 is stored
      and opens, the 503 body has the fixed message and lists file 1, files 2
      and 3 are not in the store.
- [ ] 3.1 Recovery reads through `get_original`. Proved by: a test that OCR
      recovery processes a sealed scan, and that the recovery input is read
      through the originals store (spy on `get_original`).
- [ ] 3.2 Known gap pinned. Proved by: a test that the object recovery writes
      is plaintext (no sealed header) and still reads via `get_original`; its
      docstring names `originals-ocr-sealed` as the change that inverts it.
- [ ] 4.1 Docs, which describe this behaviour and change with it:
      `docs/how-to/originals-encryption.md` (ingest order, rollback, the 503
      and the batch behaviour with the committed files, the OCR gap until
      `originals-ocr-sealed`), `docs/reference/ingest.md` (the 503 body with
      the per-file report), `docs/reference/architecture.md` (ingest order and
      readers via `get_original`), `docs/reference/cli.md` (non-zero exit on an
      unavailable key). If `originals-encrypted-ingest` already created or
      changed a file, extend it rather than duplicate. Proved by: the docs gate
      in CI.
- [ ] 4.2 `docs/reference/roadmap.yml` updated in the same PR if an item
      finishes, with evidence.
