# originals-encrypted-ingest

## Why

ADR-0008: every new original is stored sealed. `originals-cipher-and-key-store`
built the format, the key rows and `OriginalsStore`, with nothing calling it;
`deleted-document-releases-object-key` made every existence rule right. This
change switches the write at ingest and **all five readers** of an original to
`OriginalsStore` in one build, because sealing without moving every reader
would make sealed documents unreadable, and moving the readers without sealing
would protect nothing. Third change of the chain.

## What changes

- `pipeline.ingest` registers the document first, then writes through
  `put_original(session, doc.id, key, bytes)` (design.md §3a of
  `originals-cipher-and-key-store`); if anything inside `ingest` fails after the
  write, it deletes the object it wrote.
- The five readers read through `get_original`: `pipeline.process`
  (`pipeline.py:272`), `pipeline.reanonymize` (`pipeline.py:455`, also reached
  from `reprocess.py:136`), OCR recovery's input read (`recovery.py:61`), the
  redacted PDF (`api.py:736`) and the reveal PDF (`api.py:1580`). Each of
  these functions takes an `originals: OriginalsStore` where it took a
  `store`, and every caller passes one (`api.py`, `ingest_corpus.py`,
  `ingest_manifest.py`, `reprocess.py`, `serve.py`).
- `serve.py` builds one process-lifetime `OriginalsStore` (one unwrap cache)
  over a factory of `OpenBaoTransit`s, one per KEK name, in irreversible mode
  too.
- Ingest fails closed when the key service is unreachable: a named error
  (HTTP 503 at the API), the failing file not stored (#318, decided
  2026-10-31: fail closed). A batch to `POST /ingest` stops at the first
  `OriginalsKeyUnavailable`: files already ingested and committed earlier in
  that request stay stored, sealed; the failing file and every file after it
  are not stored. The 503 body keeps the fixed message `key service
  unavailable` and adds the per-file report of what already succeeded, so
  nothing is lost silently.
- One shared transit-factory helper (cached `OpenBaoTransit` per KEK name),
  used by `serve.py` and the three CLI modules; no hand-rolled copies.
- The test suite gets a `mem_originals` fixture in `tests/conftest.py`, and
  the signature changes (`originals` positional, `store=` callers) are applied
  across the ~22 test files first, as one mechanical commit. This is the only
  test work in this change: just enough to keep the existing suite green.

## Split by budget

The first build of this change failed at 194 turns having finished only the
production half. This change is narrowed to that half (ingest write, the five
readers, the transit helper, `create_app` wiring) plus the minimal test
migration. The new proof-tests and the docs move to a separate change,
`originals-encrypted-ingest-proofs`: fail closed and the batch stop, tampered
or swapped objects at the routes, legacy reads, re-ingest and crash cases, no
plaintext or key bytes in logs, the `build_app` wiring tests, and the docs
including the deploy precondition (the `document_keys` backup and the KEK
escrow exist before the first original is sealed). The requirements those
tests and docs prove move with them. The partial work is on branch
`habitat/builder/originals-encrypted-ingest-20261102-090002-12705` and may be
reused as the starting point.

## Open questions

- This change touches code and carries no docs; the docs move to
  `originals-encrypted-ingest-proofs`, so the docs gate may fail this change's
  PR. Default: the proofs change is built right after this one and brings the
  docs, and nothing is sealed on the homelab before both are deployed.

## Known gap until the next change

OCR recovery still writes its OCR'd PDF with the plain `put` (`recovery.py:78`)
until `originals-ocr-sealed`, so recovered scans are stored as legacy
plaintext in between. Their reads work (legacy objects open as they are). The
next change of the chain closes this and is built right after this one.

## Out of scope

The OCR write (next change), destroying keys on deletion
(`originals-crypto-shred`), the existing corpus (`originals-encrypt-existing`).
