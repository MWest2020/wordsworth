# originals-ingest-seam

## Why

ADR-0008: every new original is stored sealed. `originals-cipher-and-key-store`
built the format, the key rows and `OriginalsStore`, with nothing calling it.
The next step, `originals-encrypted-ingest`, tried to switch the ingest write
and all five readers in one build. Its builder failed twice (wordsworth#345:
194 and 209 turns, about $14 of a $15 budget). The production code was nearly
done both times. The budget went on renaming `store` to `originals` across
~50 test files. A proofs-only split (`originals-encrypted-ingest-proofs`,
#347) was rejected by the architect, because its tests had nothing to run
against.

This change is step 1 of 4 of the replacement. It adds the seam that makes the
rest possible **without renaming any parameter**, so the existing tests do not
change:

1. `originals-ingest-seam` (this change): the seam and the transit factory.
2. `originals-ingest-readers`: the five readers read through the seam.
3. `originals-ingest-write`: ingest writes sealed, rolls back, fails closed.
4. `originals-ingest-switch`: `serve.py` and the CLIs pass an `OriginalsStore`;
   sealing goes live; docs.

Each step leaves main green and changes nothing live until step 4.

## What changes

- `OriginalsStore` also satisfies the `ObjectStore` protocol. `put`, `delete`,
  `exists`, `get_raw` and `iter_objects` delegate to `.objects`. `get`
  delegates to the guarded plain read, so it refuses a sealed object exactly
  as before. An `OriginalsStore` can then go everywhere a `store` goes today:
  redacted-PDF cache, deletion, audit exports.
- A new module `originals_io.py` with two functions. They are the only way
  code reads or writes an original:
  - `read_original(session, store, object_key) -> bytes`: `get_original` when
    `store` is an `OriginalsStore`, else the plain `store.get`. The plain read
    of a sealed object still raises `SealedObjectError`: fail closed, no
    fallback.
  - `write_original(session, store, document_id, object_key, data) -> PutResult`:
    `put_original` when `store` is an `OriginalsStore`. Otherwise a plain `put`,
    reported as `PutResult.WROTE` when the object was absent before and as
    `PutResult.UNCHANGED` when it already existed.
- `transit.py` gains `transit_factory(url, token, timeout=10.0)`. It returns
  `transit_for(kek_name)`, which builds one `OpenBaoTransit` per KEK name and
  caches it in the closure (no module-level global).
- `serve.py`'s `_reversible_wiring` takes its pseudonymisation `Transit` from
  that factory instead of building its own `OpenBaoTransit`.
- Docs in the same PR: a reference page for the seam, linked from
  `docs/index.md`, with front matter `status` and `last_reviewed`. The first
  build's PR (#356) failed `gates / gates` for lack of it: the PR touches `src/`
  and the drift check is set to fail.

## Depends on

`originals-cipher-and-key-store` (merged). Nothing depends on this change at
runtime yet; steps 2 to 4 build on it.

## Out of scope

Calling the seam from the readers (step 2) or from ingest (step 3), and wiring
an `OriginalsStore` into the running service (step 4).
