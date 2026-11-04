---
status: draft
last_reviewed: 2026-11-04
---

# The five readers of a sealed original

Step 2 of 4 (`originals-ingest-seam` → **`originals-ingest-readers`** →
`originals-ingest-write` → `originals-ingest-switch`). Before anything is
written sealed (step 3) and the running service switches to that (step 4),
every reader of an original must already be able to open one — otherwise the
first sealed document would be unreadable. This step moves the five readers
of an original onto `read_original`
(`src/wordsworth/originals_io.py`, described in
[originals-ingest-seam](originals-ingest-seam.md)). The running service
still passes a plain store, so nothing changes live yet.

## The five readers

1. `pipeline.process` — fetches the document's bytes by its recorded key,
   lazily, the first time a step needs them.
2. `pipeline.reanonymize` — re-derives the source text from the stored bytes
   to recompute pseudonyms under the current anonymizer (also reached from
   `reprocess.py`, which calls `reanonymize` directly).
3. OCR recovery (`recovery.recover`) — fetches the scanned bytes to hand to
   the OCR engine. Its *output* write (the OCR'd text-layer PDF, under its
   own content-addressed key) stays a plain `store.put` until
   `originals-ocr-sealed` seals that too.
4. The redacted PDF route (`GET /documents/{id}/redacted.pdf`) — fetches the
   source page to render over when the redacted cache misses.
5. The reveal PDF route (`POST /documents/{id}/reveal.pdf`) — fetches the
   source page to render the granted types in clear.

None of the five change signature: the parameter is still `store`, typed
`ObjectStore`, and accepts either a plain store or an `OriginalsStore` —
`originals-ingest-seam` made the latter satisfy `ObjectStore` for exactly
this reason.

## Reads that stay plain, on purpose

Not every `store` call in these code paths is a read of an *original*, so
not every one moves:

- the redacted-PDF cache read/write (`api.py`, around the redacted-PDF
  route) — the cache holds a rendered PDF, not an original;
- the audit exports;
- deletion;
- OCR recovery's output write — the OCR'd PDF, until `originals-ocr-sealed`.

## `OriginalsKeyUnavailable` propagates

A sealed original's data key can fail to unwrap — the key service is
unreachable or refuses. `read_original` lets that exception
(`wordsworth.document_keys.OriginalsKeyUnavailable`) propagate; each of the
five readers handles it the way it already handles a store outage:

- the two PDF routes catch it around their `read_original` call and answer
  **503 `key service unavailable`**;
- `pipeline.process` and `pipeline.reanonymize` let it propagate loud and
  retryable — the document stays at its current (resumable) state, exactly
  as a store outage leaves it.

## Proof

`tests/test_originals_readers.py` builds an `OriginalsStore` over
`InMemoryObjectStore` + `DocumentKeys(FakeTransit)`, seals a PDF into it with
`write_original`, and checks that each of the five readers reaches the same
outcome a plain store gives: `process` reaches `indexed` with the same
indexed text, `reanonymize` succeeds, OCR recovery hands the engine the
plaintext scan, and both PDF routes serve a valid PDF. A separate
`OriginalsStore` sharing the same objects but bound to a refusing `Transit`
reproduces the 503 on both routes. A last test greps `src/wordsworth/` for
`store.get(doc.object_key)` / `store.get(document.object_key)` and asserts
none remain outside `originals_io.py`.
