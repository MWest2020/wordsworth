---
status: draft
last_reviewed: 2026-11-03
---

# The originals seam: `read_original` / `write_original`

ADR-0008 seals every new original under a data key wrapped by a KEK in
OpenBao Transit (`OriginalsStore`). `originals-ingest-seam` adds the seam that
lets the rest of the pipeline call through to that without caring which kind
of store it was handed: `read_original` and `write_original`
(`src/wordsworth/originals_io.py`) are the only way code reads or writes an
original. This is step 1 of 4 (`originals-ingest-seam` →
`originals-ingest-readers` → `originals-ingest-write` →
`originals-ingest-switch`); nothing calls the seam yet, and nothing live
changes until step 4.

## `read_original(session, store, object_key) -> bytes`

- Given an `OriginalsStore`, calls `get_original`: unwraps the data key and
  opens the sealed object.
- Given a plain `ObjectStore`, calls the plain `store.get`. That read keeps
  refusing a sealed object — `SealedObjectError`, no bytes returned — exactly
  as it does without the seam. There is no fallback: a plain store asked to
  read a sealed object never hands back ciphertext as if it were the
  original.

## `write_original(session, store, document_id, object_key, data) -> PutResult`

- Given an `OriginalsStore`, calls `put_original`: seals `data` under the
  object's data key (minting one if none exists yet).
- Given a plain `ObjectStore`, calls the plain `store.put` and reports the
  outcome as a `PutResult`:
  - `PutResult.WROTE` when `object_key` was absent before the write.
  - `PutResult.UNCHANGED` when `object_key` already existed.

  (`PutResult.LEGACY` is `put_original`'s own outcome for a legacy plaintext
  object it declines to overwrite; the plain path never returns it.)

## `OriginalsStore` as an `ObjectStore`

`OriginalsStore` now also satisfies the `ObjectStore` protocol, so it can go
anywhere a plain `store` goes today, for objects that are not originals
(the redacted-PDF cache, deletion, audit exports):

- `put`, `delete`, `exists`, `get_raw` and `iter_objects` delegate to the
  underlying store (`.objects`).
- `get` is the **guarded plain read** — it delegates to `.objects.get`, not
  to `get_original`, so it keeps refusing a sealed object rather than
  unwrapping one. Reading an original through the seal still requires
  `read_original` (or `get_original` directly).

## One Transit client per KEK name: `transit_factory`

`transit.transit_factory(url, token, timeout=10.0)` returns `transit_for`, a
`str -> Transit` callable that builds one `OpenBaoTransit` per KEK name and
caches it in the closure (no module-level global). Asking `transit_for` for
the same KEK name twice returns the same client; a different name gets its
own. `serve.py`'s `_reversible_wiring` takes its pseudonymisation `Transit`
from this factory instead of constructing an `OpenBaoTransit` itself —
`OpenBaoTransit(` is now built in exactly one place, `transit.py`.

See [ADR-0008](../explanation/adr/0008-envelope-encryption-of-originals.md)
for why originals are sealed at all, and
[ADR-0009](../explanation/adr/0009-separate-key-and-reveal-service.md) for the
KEK/Transit split this factory shares with the pseudonymisation path.
