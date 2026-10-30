# Tasks

A skipped test counts as failed for every reviewer.

- [ ] 1.1 `delete_document` releases the key as design.md describes: placeholder
      `deleted/<document_id>`, `released_object_key` in the `deleted` record,
      the object check made against the former key before the release. Dry run
      reports the release and changes nothing. Proved by: a test that after
      deletion the row carries the placeholder and the record the former key;
      a dry-run test.
- [ ] 1.2 A superseded copy still claiming the object keeps it: deleting the
      live document leaves the object when a copy claims it, and removes it
      when none does (existing tests stay green). Proved by: the existing
      deletion tests plus one with a superseded copy.
- [ ] 1.3 Re-ingesting a deleted document's bytes creates a new document in
      state `registered`, the deleted row stays `deleted` with its trail
      intact, and `live_document_for` returns the new one. Proved by: an
      ingest test through `pipeline.ingest`.
- [ ] 1.4 A failure during deletion leaves the real key: with the index down
      the row keeps its `object_key`, no `deleted` record exists, and a rerun
      completes and releases. Proved by: a test extending the existing
      index-down test.
- [ ] 2.1 `wordsworth-release-deleted-keys [--apply]` in `release_deleted.py`:
      lists without `--apply`, releases with it, one `release-key` audit
      record per document, a second run finds nothing; an undeleted document
      is never touched. Proved by: tests for dry run, apply, rerun, and a live
      document left alone.
- [ ] 3.1 Docs: `docs/how-to/deleting-documents.md` says a deletion releases
      the object key and that bytes can be ingested again; `docs/reference/cli.md`
      lists `wordsworth-release-deleted-keys` with the instruction to run it
      once after deploying this change. Proved by: the docs gate.
