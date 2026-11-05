# Tasks

Step 3 of 4. Depends on `originals-ingest-readers` being merged: check that
`pipeline.process` reads through `read_original`, and stop if it does not.
No existing test changes. A skipped test counts as failed. Tests use
`FakeTransit`, the in-memory store and an `OriginalsStore` over them.

- [x] 1.1 Register first. Proved by `tests/test_originals_ingest.py`: a spy
      `OriginalsStore` records whether the document row is already in the
      session when `put_original` is called. It is, and the key row's
      `document_id` is the registered document's id.
- [x] 1.2 Rollback deletes only what this call wrote. Proved by the same file:
      - the dossier add fails after `PutResult.WROTE`: no object and no
        document remain;
      - the same bytes are ingested for a live document (`UNCHANGED`) and a
        later step fails: the existing object is still stored and still opens.
- [x] 1.3 Sealed at rest. Proved by the same file: an ingest to an
      `OriginalsStore` stores an object that starts with the sealed header,
      does not contain the PDF's text, and opens to the ingested bytes.
      Ingesting identical bytes twice gives one document, one key row and an
      unchanged object.
- [x] 2.1 Fail closed at the API, both modes. Proved by
      `tests/test_ingest_fail_closed.py`: `create_app(store=<OriginalsStore
      over a refusing FakeTransit>)` in reversible and in irreversible mode,
      one PDF to `POST /ingest`: 503, `detail` is `key service unavailable`,
      and the store holds no object.
- [x] 2.2 Batch stop. Proved by the same file, with a three-file batch whose
      transit refuses from the second file on:
      - file 1 is stored, sealed, and opens;
      - the 503 body has the fixed `detail`, `total` 3, and `results` with
        exactly file 1;
      - files 2 and 3 are not in the store.
- [x] 2.3 Other errors still continue. Proved by: the existing batch tests
      passing unchanged, and the corrected `ingest_documents` docstring.
- [x] 2.4 Read-back refusal leaves the object. Proved by
      `tests/test_ingest_fail_closed.py`: the write commits, then `process`'s
      read-back raises `OriginalsKeyUnavailable`: 503, and the sealed object
      is still stored (no delete is called on the `process` path).
- [x] 3.1 CLIs exit non-zero. Proved by: a test of each of `ingest_corpus` and
      `ingest_manifest` with a refusing transit: non-zero exit, the message on
      stderr, and no second file attempted.
- [x] 4.1 Suite and lint. Proved by: the full suite passes with no new skips,
      and `uv run ruff check src/ tests/` is clean.
- [x] 5.1 Docs change with the behaviour. Proved by `grep -n "key service
      unavailable" docs/reference/ingest.md docs/reference/cli.md` finding
      the new text in both:
      - `docs/reference/ingest.md`: a section on the 503 body (`detail`,
        `total`, `indexed`, `results`) and which files are stored;
      - `docs/reference/cli.md` (line 87, "A file that fails does **not**
        abort the batch"): names the key-service exception and the CLI exit.
