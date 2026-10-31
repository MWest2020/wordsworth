# Design

The decisions behind this change are in `originals-cipher-and-key-store`
design.md (points 1 to 6, §3a and "Availability"). What is specific here:

## Ingest order

```
digest = sha256(bytes); key = "documents/" + digest
doc = register_live(session, key, ...)        # id first; flush
wrote = originals.put_original(session, doc.id, key, bytes)
try:   dossier membership, as today
except: if wrote: store.delete(key); raise
```

Registering first is needed because the key row carries the document id. A
re-ingest of a live document's bytes finds its row and its sealed object and
writes nothing (rule 1); a re-ingest of a live **legacy** document's bytes
leaves the plaintext object for `originals-encrypt-existing` (rule 4). The
callers' commit stays where it is; a commit that fails after the write leaves
an object that opens under no row, which the next ingest of the same bytes
repairs and `wordsworth-sealed-orphans` removes.

The already-indexed shortcut in `api.py` (`has_object_key`) reads no original
and stays as it is.

## One way to read

`process`, `reanonymize` and `recover` take `originals: OriginalsStore` in
place of `store: ObjectStore`, and the two PDF routes read
`originals.get_original(session, doc.object_key)`. Renaming the parameter (rather than
passing an `OriginalsStore` where an `ObjectStore` is typed) makes a missed
caller a type and test failure, not a runtime surprise; the plain-`get` guard
of the previous change catches whatever a test still misses. `OriginalsStore`
exposes the underlying store as `.objects` for deletion and the sweep, which
remove objects and never read originals. Each call passes the caller's
session (`originals-cipher-and-key-store` §3a "Sessions"); the
`OriginalsStore` itself holds none, so one instance serves the whole process.

The cached redacted PDF (`api.py:733`, `redacted_cache_key`) and the stored
audit exports stay plain objects: they are derived, de-identified bytes, not
originals, and are read with the plain `get` as today.

`recover` reads its input through `get_original` here; its write moves in
`originals-ocr-sealed`.

## Availability

`OriginalsKeyUnavailable` at ingest maps to HTTP 503 with a fixed message
(`"key service unavailable"`), in reversible and irreversible mode; the CLIs
exit non-zero with the same message. At read, the PDF routes answer 503 the
same way; `process` and `reanonymize` let it propagate (loud, retryable), as
they do for a store outage. There is no setting that turns sealing off: if
Mark decides otherwise on #318, a follow-up change adds one explicitly.

## Deploy precondition

Sealing makes the key rows and the KEK as critical as the objects: lose
either and the originals are lost. The how-to
`docs/how-to/originals-encryption.md` states the precondition, and the deploy
of this version on the homelab links its evidence:

1. the Postgres backup includes `document_keys`, and one restore of it was
   tested;
2. an OpenBao snapshot that contains the Transit KEK exists off the node.

## Files

`pipeline.py` and `api.py` are already past 200 lines; this change only
replaces calls in them and adds no function to either. New wiring goes in
`serve.py` and the CLI modules.
