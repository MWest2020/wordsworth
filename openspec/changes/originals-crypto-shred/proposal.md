# originals-crypto-shred

## Why

ADR-0008: deleting a document must make its original unreadable everywhere,
including in backups and replicas that still hold the object. Destroying the
document's data key does that (crypto-shredding).

## What changes

- Deleting a document (document or dossier deletion) destroys its wrapped data
  key, unless another live document still references the same key (a
  de-duplicated original), in addition to removing the object.
- The `deleted` audit record counts the destroyed key (never the key itself).
- Dry run reports whether the key would be destroyed or kept (shared).

## Depends on

`originals-envelope-encryption`.
