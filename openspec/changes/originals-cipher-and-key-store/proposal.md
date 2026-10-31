# originals-cipher-and-key-store

## Why

ADR-0008 (accepted 2026-10-30) seals every original PDF under its own data key.
The first attempt, `originals-envelope-encryption` (#306), failed at the
architect twice: it was 19 tasks across a cipher, a key store, an ingest
reordering, five read sites and OCR recovery, and on five points a builder had
to guess. It is replaced by four changes along the architect's own seams; this
is the first. It builds the parts every later change stands on, and changes
no ingest or read path yet: nothing is sealed in production after this build.

## What changes

- A new module `src/wordsworth/originals_envelope.py`: the sealed-object format
  (header) and `seal` / `open` (AES-256-GCM), with the associated data fixed in
  design.md. Nothing else lives there: the 200-line limit decides the split.
- A new `document_keys` table and `DocumentKeys` store
  (`src/wordsworth/document_keys.py`): one row per sealed **object**, holding
  the data key wrapped by the KEK (OpenBao Transit), never in clear.
- `OriginalsStore` in its own module `src/wordsworth/originals_store.py` (the
  class name is the public import): `put_original(session, document_id,
  object_key, data)` and `get_original(session, object_key)` over the existing
  `ObjectStore`, with the `put_original` rules of design.md §3a. Nothing calls
  it yet.
- `put_original` returns a `PutResult` enum (`WROTE`, `UNCHANGED`, `LEGACY`),
  not a bool or a string. Callers delete the object they wrote only on
  `wrote is PutResult.WROTE`. The enum has no truthiness (`__bool__` raises),
  so `if wrote:` cannot become a wrong delete. The sibling changes
  `originals-encrypted-ingest` and `originals-ocr-sealed` are coded to that
  form (task 7.1).
- `ObjectStore.get_raw` and `ObjectStore.iter_objects`, added to the protocol
  and to both drivers in the same commit, and a guard in the plain
  `ObjectStore.get`: an object
  that carries the sealed header is refused with `SealedObjectError`, so no
  caller can ever receive ciphertext as if it were a PDF.
- A downgrade guard in `get_original`: an object whose key has a
  `document_keys` row but carries no header is refused.
- The unwrap cache rule (design.md), configuration of the KEK per
  pseudonymisation domain, and a sweep for sealed objects that have no key row
  (`wordsworth-sealed-orphans`, dry-run by default).

## Order of the chain

`originals-cipher-and-key-store` (this) → `deleted-document-releases-object-key`
→ `originals-encrypted-ingest` → `originals-ocr-sealed` → `originals-crypto-shred`
→ `originals-encrypt-existing`.

## Out of scope

Ingest, the read sites and OCR recovery (the next three changes); migrating
existing objects; deletion of keys; the separate key service (ADR-0009).
