# Tasks

Step 4 of 4. Depends on `originals-ingest-write` being merged: check that
`pipeline.ingest` calls `write_original`, and stop if it does not. A skipped
test counts as failed.

- [x] 1.1 `serve.build_app` passes one `OriginalsStore` as `store`, in both
      modes. The mechanism: `build_app` sets `app.state.store` and
      `app.state.transit_for`. Proved by `tests/test_originals_switch.py`: with
      S3 and OpenBao settings monkeypatched and `S3ObjectStore.from_config`
      stubbed, `app.state.store` is an `OriginalsStore`, in reversible and in
      irreversible mode, and the reversible key provider shares
      `app.state.transit_for`. The test and the reviewer use that surface and
      no private attributes.
- [x] 1.2 `originals_io.originals_from_config` is used by `ingest_corpus.py`
      and `ingest_manifest.py`. `reprocess.py` is left out: it builds no store
      and has no entry point; its store comes from `build_app` (task 1.1).
      Proved by: the same file asserts each of the two CLIs' store is an
      `OriginalsStore` (stubbed backends), and
      a grep finds `OpenBaoTransit(` in `src/` only in `transit.py`.
- [x] 2.1 The OCR gap is pinned. Proved by `tests/test_ocr_gap.py`: the object
      recovery writes has no sealed header and opens through `read_original`.
      The docstring names `originals-ocr-sealed`.
- [x] 3.1 Docs: `docs/how-to/originals-encryption.md` (new),
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
- [x] 3.2 `docs/reference/roadmap.yml`: the item "New originals stored
      encrypted …" set to done, with this change as evidence. The item text
      and the evidence must not say that new originals are encrypted now: they
      say the code seals new originals, and that new documents are encrypted
      only after the homelab digest bump and stay plaintext until then, as in
      the deploy precondition section of proposal.md. Proved by: the roadmap
      check in CI, and a grep of the item for the digest-bump statement.
- [ ] 3.3 `docs/reference/cli.md` lines 88-94 (the "known gap tracked for
      `originals-ingest-switch`" sentence): say the gap, that the CLI does not
      stop the run on a 503 `key service unavailable`, lives in `client.py`
      (its retry handling, `client.py:178-184`), is not fixed in this change,
      and link the follow-up issue. Proved by: a grep of `cli.md` that finds
      no mention of `originals-ingest-switch` as tracker and finds the issue
      link, and the docs gate in CI.
      BLOCKED (builder, 2026-11-09): `cli.md` is corrected to name `client.py`
      (`client.py:178-184`) as the gap's home and drop the
      `originals-ingest-switch` tracker attribution, but no follow-up issue
      exists to link -- `gh` is denied in this sandbox, and filing a
      cross-repo GitHub issue is a visible-to-others action this role should
      not take without sign-off anyway. Mark (or a session with `gh` access)
      needs to file the issue and drop its link into the `TODO` left in
      `cli.md`; this checkbox stays unchecked until that link exists.
- [x] 4.1 Suite and lint. Proved by: the full suite passes with no new skips,
      and `uv run ruff check src/ tests/` is clean.
