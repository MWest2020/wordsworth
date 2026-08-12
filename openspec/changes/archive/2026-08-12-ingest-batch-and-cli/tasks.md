## 1. Batch ingest

- [x] 1.1 `POST /ingest` accepts `files: list[UploadFile]` (one or many).
- [x] 1.2 Per-file result; a failing file is recorded and does not abort the
  batch; errors carry only the exception class, never document text.
- [x] 1.3 Typed `IngestResponse` `{total, indexed, results[]}`.

## 2. Client CLI

- [x] 2.1 `wordsworthctl` (stdlib-only): health / ingest / search / state.
- [x] 2.2 `ingest` walks a dir (`*.pdf` or `--all`), batches, prints summary.
- [x] 2.3 `wordsworthctl` console script; offline tests (iteration, missing path).

## 3. Docs + gate

- [x] 3.1 Route summaries/docstrings/tags + app description/version.
- [x] 3.2 Full suite green (156 passed) + `openspec validate --all`.
