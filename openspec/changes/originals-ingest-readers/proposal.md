# originals-ingest-readers

## Why

Step 2 of 4 (`originals-ingest-seam` → **`originals-ingest-readers`** →
`originals-ingest-write` → `originals-ingest-switch`). Before anything is
written sealed, every reader of an original must be able to open one.
Otherwise the first sealed document would be unreadable. This step moves the
five readers onto `read_original`. The running service still passes a plain
store, so nothing changes live.

## What changes

The five readers of an original call
`originals_io.read_original(session, store, doc.object_key)` instead of
`store.get(doc.object_key)`:

1. `pipeline.process` (`pipeline.py:272`);
2. `pipeline.reanonymize` (`pipeline.py:455`, also reached from
   `reprocess.py`);
3. OCR recovery's input read (`recovery.py:61`);
4. the redacted PDF route (`api.py:736`);
5. the reveal PDF route (`api.py:1580`).

No signature changes. The parameter stays `store` and accepts a plain store or
an `OriginalsStore`, since step 1 made the latter satisfy `ObjectStore`.

Reads that are not of originals stay plain `store` calls on purpose:
- the redacted-PDF cache (`api.py:732-749`);
- the audit exports;
- deletion;
- recovery's OCR write. That write goes plain until `originals-ocr-sealed`.

`OriginalsKeyUnavailable` raised by a read propagates:
- the two PDF routes map it to 503 `key service unavailable`;
- `process` and `reanonymize` let it propagate, loud and retryable, as they do
  for a store outage.

## Depends on

`originals-ingest-seam` (`read_original`, and `OriginalsStore` satisfying
`ObjectStore`).

## Out of scope

The ingest write (step 3) and the wiring (step 4).
