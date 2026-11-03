# Tasks

Step 2 of 4. Depends on `originals-ingest-seam` being merged: check that
`src/wordsworth/originals_io.py` exists, and stop if it does not. No existing
test changes. A skipped test counts as failed. Tests use `FakeTransit`, the
in-memory store, and an `OriginalsStore` built over them in the test.

- [ ] 1.1 `pipeline.process` and `pipeline.reanonymize` read through
      `read_original`. Proved by `tests/test_originals_readers.py`: a document
      whose original was written sealed with `write_original` to an
      `OriginalsStore` reaches `indexed` through `process`, and
      `reanonymize` of it succeeds. The document's text in the index equals
      that of the same PDF processed from a plain store.
- [ ] 1.2 OCR recovery reads its input through `read_original`. Proved by the
      same file: a sealed scan in `unprocessable_ocr` is recovered with a stub
      OCR engine, and the engine receives the plaintext bytes.
- [ ] 1.3 The two PDF routes read through `read_original` and map
      `OriginalsKeyUnavailable` to 503 `key service unavailable`. Proved by
      the same file:
      - `create_app(store=<OriginalsStore>)` serves the redacted PDF and the
        reveal PDF of a sealed document (200, a valid PDF);
      - with a `Transit` that refuses, the redacted PDF route answers 503 with
        that message.
- [ ] 1.4 No plain read of an original remains. Proved by: a test (in the same
      file) that greps `src/wordsworth/` for `.get(doc.object_key)` and
      `.get(document.object_key)` and finds none outside `originals_io.py`.
- [ ] 2.1 Suite and lint. Proved by: the full suite passes with no new skips,
      and `uv run ruff check src/ tests/` is clean.
