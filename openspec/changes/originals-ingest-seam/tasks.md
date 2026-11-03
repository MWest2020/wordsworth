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
- [ ] 3.1 Docs, in the same PR as the code. The PR touches `src/`, so the
      `docs-gates` drift check (`drift_mode: fail`) fails without a change under
      `docs/`; the `docs-drift-ok` label does not fit, because the seam is new
      behaviour. Write:
      - `docs/reference/originals-ingest-seam.md`: `read_original` and
        `write_original` (what each does for an `OriginalsStore` and for a plain
        store, `PutResult.WROTE`/`UNCHANGED`, the plain read of a sealed object
        raising `SealedObjectError`) and `transit_factory` (one client per KEK
        name). Markdown only under `how-to/`, `reference/` or `explanation/`.
      - front matter on the new page: `status` and `last_reviewed` (today's
        date); the contract gate refuses a page without it.
      - a link to the page in `docs/index.md` under the reference section, and
        bump that file's `last_reviewed`.
      Proved by: the `gates / gates` check (drift and contract) passing on the
      PR, and `docs/reference/originals-ingest-seam.md` existing with front
      matter and being linked from `docs/index.md`.
- [ ] 4.1 Suite and lint. Proved by: the full suite passes with no new skips,
      and `uv run ruff check src/ tests/` is clean.
