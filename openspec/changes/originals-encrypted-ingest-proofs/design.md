# Design

Choices of the production design are in `originals-encrypted-ingest`
design.md and `originals-cipher-and-key-store` design.md. What is specific
here is how the proofs are made.

## Tests use the fakes, and read the artefact

Tests use `FakeTransit`, the in-memory store and the `mem_originals` fixture.
Assertions look at what was produced (the stored object's bytes, the key rows,
the response body), not at a re-run of the logic. A skipped test counts as
failed.

## Register-first is proved by order, not by outcome

A spy store records the call order: the document row is flushed before
`put_original` is called, and the key row's `document_id` equals the
registered document. Rejected: asserting only the end state, which a
write-first implementation with a later fix-up would also satisfy.

## Rollback deletes only what this call wrote

When ingest fails after the write, the object is deleted only if
`put_original` returned `PutResult.WROTE`. A re-ingest that found an existing
object returns another result and its object is left alone, because it belongs
to a live document. The tests cover both sides.

## Batch stops at the first key failure

As decided in `originals-encrypted-ingest`: files committed before the failure
stay stored and sealed, the failing file and later ones are not stored, the
503 body keeps `key service unavailable` and lists the committed files.
Rejected there, and not revisited: rolling back earlier files, and continuing
past the failure.

## Known gap pinned by a test

OCR recovery writes with the plain `put` until `originals-ocr-sealed`. A test
states this so the next change has to change it on purpose; it asserts that the
recovered object is legacy plaintext and that it still reads. That test is
removed or inverted by `originals-ocr-sealed`.
