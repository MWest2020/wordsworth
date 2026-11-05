# Tasks

Step 4 of 4. Depends on `originals-ingest-write` being merged: check that
`pipeline.ingest` calls `write_original`, and stop if it does not. A skipped
test counts as failed.

- [ ] 1.1 `serve.build_app` passes one `OriginalsStore` as `store`, in both
      modes. Proved by `tests/test_originals_switch.py`: with S3 and OpenBao
      settings monkeypatched and `S3ObjectStore.from_config` stubbed, the app's
      store is an `OriginalsStore`, in reversible and in irreversible mode,
      and the reversible key provider shares its `transit_for`. `build_app`
      exposes the shared `transit_for` factory and the test asserts on that;
      it does not read private attributes.
- [ ] 1.2 `originals_io.originals_from_config` is used by `ingest_corpus.py`
      and `ingest_manifest.py`. `reprocess.py` is left out: it builds no store
      and has no entry point; its store comes from `build_app` (task 1.1).
      Proved by: the same file asserts each of the two CLIs' store is an
      `OriginalsStore` (stubbed backends), and
      a grep finds `OpenBaoTransit(` in `src/` only in `transit.py`.
- [ ] 2.1 The OCR gap is pinned. Proved by `tests/test_ocr_gap.py`: the object
      recovery writes has no sealed header and opens through `read_original`.
      The docstring names `originals-ocr-sealed`.
- [ ] 3.1 Docs: `docs/how-to/originals-encryption.md` (new),
      `docs/reference/ingest.md`, `docs/reference/architecture.md`,
      `docs/reference/cli.md`, as in proposal.md, including the deploy
      precondition. The how-to states that an empty `openbao_token` or an
      unreachable OpenBao gives 503 on every ingest, by design (no plaintext
      fallback), with rollback via the previous homelab image digest. It also
      says the `document_keys` backup and the off-node KEK snapshot are deploy
      preconditions in the homelab PR, not build tasks. Proved by: the docs
      gate in CI, and a grep of the how-to for those statements. The 503 body
      in the docs is the one the code returns; read it from `api.py`, don't
      retype it.
- [ ] 3.2 `docs/reference/roadmap.yml`: the item "New originals stored
      encrypted …" set to done, with this change as evidence. Proved by: the
      roadmap check in CI.
- [ ] 4.1 Suite and lint. Proved by: the full suite passes with no new skips,
      and `uv run ruff check src/ tests/` is clean.
