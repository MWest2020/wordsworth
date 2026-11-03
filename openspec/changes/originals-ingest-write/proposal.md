# originals-ingest-write

## Why

Step 3 of 4 (`originals-ingest-seam` → `originals-ingest-readers` →
**`originals-ingest-write`** → `originals-ingest-switch`). With every reader
able to open a sealed original, ingest may now write one. The behaviour below
was decided in the original `originals-encrypted-ingest`; it moves here
unchanged. It still changes nothing live, because the running service passes
a plain store until step 4.

## What changes

- **Register first.** `pipeline.ingest` registers the document before it
  writes, because the key row carries the document id. It then writes through
  `originals_io.write_original(session, store, doc.id, key, bytes)`. If
  anything inside `ingest` fails after the write returned `PutResult.WROTE`,
  it deletes that object. An object it did not write (`UNCHANGED`, or
  `LEGACY` for a live legacy document) is never deleted. Ingest order (from
  `originals-cipher-and-key-store` §3a):
  ```
  digest = sha256(bytes); key = "documents/" + digest
  doc = register_live(session, key, ...)            # id first; flush
  wrote = write_original(session, store, doc.id, key, bytes)
  try:   dossier membership, as today
  except: if wrote is PutResult.WROTE: store.delete(key); raise
  ```
- **Fail closed** (#318, decided 2026-10-31).
  - `OriginalsKeyUnavailable` stops ingest with a named error, in reversible
    and irreversible mode, and there is no plaintext fallback.
  - At `POST /ingest`, the batch stops at the first `OriginalsKeyUnavailable`,
    whether raised by the write or by `process` reading back:
    - files completed earlier in the request stay stored and sealed;
    - the failing file and every file after it are not stored.
  - The response is HTTP 503 with this body (decided here: the earlier change
    left the shape open, and the architect asked for it to be fixed):
    ```json
    {"detail": "key service unavailable",
     "total": <files in the request>,
     "indexed": <count of "indexed" among results>,
     "results": [<the IngestResult of every file before the failing one>]}
    ```
  - `detail` is the fixed string, so existing clients that read `detail` keep
    working. `results` has the same per-file shape as the 200 response.
  - Every other per-file error still continues the batch, as today.
  - The docstring of `ingest_documents` (`api.py:1145-1148`, "a failing file
    does not abort the batch") is corrected to name this one exception.
- **CLIs.** `ingest_corpus.py` and `ingest_manifest.py` exit non-zero with
  `key service unavailable` on `OriginalsKeyUnavailable`, and do not go on to
  the next file.

## Depends on

`originals-ingest-readers`, so that nothing written sealed is unreadable.

## Out of scope

Wiring an `OriginalsStore` into `serve.py` and the CLIs (step 4), the OCR
write (`originals-ocr-sealed`), and the docs (step 4).
