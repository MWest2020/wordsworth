# Tasks

A skipped test counts as failed for every reviewer. Order per design.md "Order
of work". The new proof-tests and the docs are in
`originals-encrypted-ingest-proofs`, not here. The partial work on branch
`habitat/builder/originals-encrypted-ingest-20261102-090002-12705` may be the
starting point.

- [ ] 1.1 Test scaffolding, one mechanical commit, first: a `mem_originals`
      fixture in `tests/conftest.py`, and the positional and `store=` signature
      changes (`originals` replacing `store`) across the ~22 test files that
      call `process`, `reanonymize`, `recover`, `ingest` or `create_app`.
      Proved by: the existing suite passes unchanged in behaviour (same tests,
      same results, no skips added) and `grep -rn "store=" tests/` finds no
      caller of the changed functions.
- [ ] 2.1 One shared transit-factory helper returning `transit_for(kek_name)`
      with one cached `OpenBaoTransit` per KEK name, written before its users.
      Proved by: the existing suite stays green and a grep that
      `OpenBaoTransit(` appears in `src/` only inside the helper.
- [ ] 2.2 `serve.py` and the three CLI modules (`ingest_corpus.py`,
      `ingest_manifest.py`, `reprocess.py`) all use the helper; none builds a
      transit itself. Proved by: the same grep.
- [ ] 3.1 The five readers read through `get_original`, with `originals`
      replacing `store` in `process`, `reanonymize` and `recover` and in every
      caller (`api.py`, `ingest_corpus.py`, `ingest_manifest.py`,
      `reprocess.py`, `serve.py`); `reprocess.py` passes `originals` where it
      passed `store`. OCR recovery's write stays the plain `put`. Proved by:
      the existing suite passes and a grep that `.get(doc.object_key)` and
      `.get(document.object_key)` appear nowhere in `src/`.
- [ ] 4.1 `pipeline.ingest` registers first, then `put_original`; if `ingest`
      fails after a `WROTE` result it deletes the object it wrote. Proved by:
      the existing ingest tests, migrated in 1.1, pass.
- [ ] 4.2 Ingest fails closed: `OriginalsKeyUnavailable` maps to HTTP 503
      `key service unavailable` at the API and a non-zero exit in the CLIs. A
      batch to `POST /ingest` stops at the first failure; the 503 body keeps the
      fixed message and adds the per-file report of files already committed.
      Proved by: the existing suite passes and a manual run of `/ingest`
      against a Transit that refuses, showing the 503 body and no stored
      object.
- [ ] 5.1 `create_app` and `serve.py` build one process-lifetime
      `OriginalsStore` in both modes over the helper's `transit_for`, and pass
      it on. Proved by: the existing suite passes and
      `uvx ruff check src/ tests/` is clean.
