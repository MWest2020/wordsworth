# originals-encrypt-existing

## Why

ADR-0008: after `originals-encrypted-ingest` and `originals-ocr-sealed`, new originals are sealed; the
existing corpus (about 420 objects on the homelab) is still plaintext. This
change seals it, verifiably, without losing a document.

## What changes

- A CLI `wordsworth-seal-originals [--dry-run] [--ids ...]`: for each live
  document with a legacy plaintext original, read, seal under a new data key,
  write the sealed object, verify that it opens to bytes with the recorded
  SHA-256, and only then remove the plaintext object.
- Before/after report: object count, sealed/legacy counts, bytes; per document
  verified or failed; never content.
- Idempotent and resumable: a document already sealed is skipped.

## Depends on

`originals-crypto-shred` (chain order; it replaced `originals-envelope-encryption`
together with the four changes before it).
