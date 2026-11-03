# Tasks

Step 1 of 4: `originals-ingest-seam` → `originals-ingest-readers` →
`originals-ingest-write` → `originals-ingest-switch`. No existing test changes:
no parameter is renamed. A skipped test counts as failed for every reviewer.
Tests use `FakeTransit` and the in-memory store.

- [ ] 1.1 `OriginalsStore` satisfies `ObjectStore`: `put`, `delete`, `exists`,
      `get_raw` and `iter_objects` delegate to `.objects`, and `get` is the
      guarded plain read. Proved by: `tests/test_originals_io.py`. An
      `OriginalsStore` over `InMemoryObjectStore` round-trips a plain object
      through `put`/`get`/`exists`/`delete`, and `get` of an object sealed
      with `put_original` raises `SealedObjectError`.
- [ ] 1.2 `originals_io.read_original` and `write_original`. Proved by the same
      file:
      - with a plain `InMemoryObjectStore`, a write then a read returns the
        bytes; the first write reports `PutResult.WROTE` and the second
        `PutResult.UNCHANGED`;
      - with an `OriginalsStore`, a write stores a sealed object (header
        present, plaintext absent) that `read_original` opens to the original
        bytes;
      - `read_original` with a plain store of a sealed object raises
        `SealedObjectError`.
- [ ] 2.1 `transit.transit_factory`. Proved by `tests/test_transit_factory.py`:
      the same name returns the same client object, two names return two, and
      each client carries its own KEK name. No network: monkeypatch `httpx`.
- [ ] 2.2 `serve._reversible_wiring` uses the factory. Proved by: a grep that
      `OpenBaoTransit(` appears in `src/` only inside `transit.py`, and the
      existing suite passing unchanged.
- [ ] 3.1 Suite and lint. Proved by: the full suite passes with no new skips,
      and `uvx ruff check src/ tests/` is clean.
