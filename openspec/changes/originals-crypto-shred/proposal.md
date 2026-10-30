# originals-crypto-shred

## Why

ADR-0008: deleting a document must make its original unreadable everywhere,
including in backups and replicas that still hold the object. Destroying the
document's data key does that (crypto-shredding).

## What changes

- Deleting a document (document or dossier deletion) destroys its wrapped data
  key, unconditionally, in addition to removing the object. Per
  `originals-cipher-and-key-store` (one key row per object, owned by the live
  document) and `deleted-document-releases-object-key`,
  `uq_documents_live_object_key` allows only
  one live document per object key, so a key is never shared by a live
  document and there is no "keep it while another document uses it" case.
- The `deleted` audit record counts the destroyed key (never the key itself).
- Dry run reports that the key would be destroyed.

## Depends on

`originals-ocr-sealed` (the chain `originals-cipher-and-key-store` →
`deleted-document-releases-object-key` → `originals-encrypted-ingest` →
`originals-ocr-sealed`, which replaced `originals-envelope-encryption`).
