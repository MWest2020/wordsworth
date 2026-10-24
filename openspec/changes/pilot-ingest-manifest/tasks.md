# Tasks

## 1. Manifest format and parsing
- [x] Define the shared record (`file`, `url`, `fetched_at`, `sha256`, `bytes`,
      `status`, `ok` per file) and a
      reader/writer used by both the fetcher and `ingest_corpus.py`.
      Proved by: test 2 (a record written as the fetcher writes it is ingested).
      (`src/wordsworth/manifest.py`: `ManifestEntry`, `write_record`, `read_manifest`.)
- [x] `fetch_woo_corpus.py` writes the shared record. Proved by: test 2.
      (Additive: the shared fields ride alongside `bestand`/`bron`/`besluit`/
      `opgehaald`, which `wordsworth-dossier-uit-herkomst` and the ranking-eval
      tooling still key on — out of scope for this change.)

## 2. `--manifest` in `ingest_corpus.py`
- [x] A `*.pdf` without an entry aborts the whole run before any ingest.
      Proved by: test 3.
- [x] sha256 of each file checked against its entry. Proved by: test 4.
- [x] `source_url` and the manifest's `fetched_at` passed to `ingest()`; the
      ingest time is never substituted. Proved by: test 1.
- [x] Read-back of the `register` audit record after each ingest; mismatch or
      absence fails that document with the reason and the exit status is
      non-zero. Proved by: tests 1 and 5 (same dossier and another dossier).

## 3. Guards
- [x] Required `WORDSWORTH_BACKEND_ENV` (`homelab|alma`), no default, not
      inferred from URLs: missing, empty, unknown or `alma` is refused. Proved
      by: test 6.
- [x] A layer that did not run fails the run, OpenAnonymiser down included.
      Proved by: test 7.
- [x] A manifest whose pilot report lacks a completed check (who, when, quoted
      robots.txt and terms, Anubis status, decision `proceed`) is refused.
      Proved by: test 8.

## 3b. Layout and hygiene (the reviewer's findings)
- [x] `ingest_manifest_corpus`, `_advance` and the manifest logic in their own
      module; `src/wordsworth/ingest_corpus.py` keeps only CLI wiring; every
      file ≤200 lines. Proved by: `wc -l` on the touched files in the PR text,
      and the existing and new ingest tests still passing.
      (`ingest_corpus.py` 120, `ingest_manifest.py` 184, `manifest.py` 87.)
- [x] No scratch or verification artefacts committed (no `.scratch-verify/`,
      no manifest, no `check.json`). Proved by: `git diff --stat main` in the PR
      text shows none.
- [x] `docs/explanation/meting-woo-corpus-01.herkomst.jsonl` uses `file`, `url`,
      `fetched_at`. Proved by: test 2 reads the sample, and a grep for
      `bron`/`opgehaald`/`bestand` in the file finds nothing.

## 3c. Test correction (CI finding on PR #217)
- [x] `test_openanonymiser_down_fails_the_run` asserts `rc == 1` and that
      nothing is indexed, not `State.EXTRACTED` (a failed anonymize leaves the
      document `REGISTERED`). Proved by: the test passing against a real
      Postgres (`WORDSWORTH_TEST_DATABASE_URL`) with the test not skipped, and
      CI's Fast test gate (offline) green.
      (Built correct the first time; no `State.EXTRACTED` assertion ever existed.)

## 4. Tests (`tests/test_ingest_corpus.py`, the design.md list)
- [x] Tests 1 to 8 from `design.md`, integration through `ingest_corpus`.
      Database tests: use a private test database
      (`WORDSWORTH_TEST_DATABASE_URL`) and report which tests skipped.
      (12 passed, 0 skipped: `uv run pytest tests/test_ingest_corpus.py -q`.)

## 5. Docs (must change with the code; CI fails on code without docs)
- [x] `docs/reference/ingest.md`: the manifest format, the required
      `WORDSWORTH_BACKEND_ENV`, the read-back, and that
      a duplicate delivery keeps its first provenance and fails the run.
      Proved by: a docs review in the PR; the page names `--manifest`.
- [x] `docs/reference/evaluation.md`, section "The published-dossier pilot":
      the gate order (check, then manifest, then ingest) and the layer rule.
- [x] `docs/reference/cli.md`: the `wordsworth-ingest --manifest` option.

## 6. Verification
- [x] Run the installed `wordsworth-ingest` from the side without the key:
      once with an unlisted file, once with `WORDSWORTH_BACKEND_ENV=alma` and
      once with it unset, and see all three refused. Ingest nothing from
      `~/wordsworth-pilot` (frozen). Proved by: the commands and output in the PR description.

## 7. Later, not this change
- Recording provenance on re-delivery (own OpenSpec change).
- `pilot-report-template`, the pilot ingest run itself, and the gold-set
  tooling.
