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
  `put_original(doc.id, key, bytes)` (design.md §3a of
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
  over the existing `OpenBaoTransit`, in irreversible mode too.
- Ingest fails closed when the key service is unreachable: a named error
  (HTTP 503 at the API), nothing stored (Mark's call on #318; this is its
  default).
- Docs, including the deploy precondition: the `document_keys` backup and the
  KEK escrow exist before the first original is sealed.

## Known gap until the next change

OCR recovery still writes its OCR'd PDF with the plain `put` (`recovery.py:78`)
until `originals-ocr-sealed`, so recovered scans are stored as legacy
plaintext in between. Their reads work (legacy objects open as they are). The
next change of the chain closes this and is built right after this one.

## Out of scope

The OCR write (next change), destroying keys on deletion
(`originals-crypto-shred`), the existing corpus (`originals-encrypt-existing`).
