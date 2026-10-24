# Tasks

## 1. Manifest format and parsing
- [ ] Define the shared record (`file`, `url`, `fetched_at`, `sha256`, `bytes`,
      `status`, `ok` per file) and a
      reader/writer used by both the fetcher and `ingest_corpus.py`.
      Proved by: test 2 (a record written as the fetcher writes it is ingested).
- [ ] `fetch_woo_corpus.py` writes the shared record next to its existing
      `bestand`/`bron`/`opgehaald`/`besluit` keys, not instead of them. Proved
      by: tests 2 and 8.

## 2. `--manifest` in `ingest_corpus.py`
- [ ] A `*.pdf` without an entry aborts the whole run before any ingest.
      Proved by: test 3.
- [ ] sha256 of each file checked against its entry. Proved by: test 4.
- [ ] `source_url` and the manifest's `fetched_at` passed to `ingest()`; the
      ingest time is never substituted. Proved by: test 1.
- [ ] Read-back of the `register` audit record after each ingest; mismatch or
      absence fails that document with the reason and the exit status is
      non-zero. Proved by: tests 1 and 5 (same dossier and another dossier).

## 3. Guards
- [ ] Required `WORDSWORTH_BACKEND_ENV` (`homelab|alma`), no default, not
      inferred from URLs: missing, empty, unknown or `alma` is refused. Proved
      by: test 6.
- [ ] A layer that did not run fails the run, OpenAnonymiser down included.
      Proved by: test 7.
- [ ] The gate reads `check.json` in the manifest's directory and passes only
      when `checked_by`, `checked_at` (ISO-8601 with timezone),
      `robots_txt_url`, `robots_txt`, `paths_used`, `paths_disallowed_used`,
      `terms`, `anubis`, `user_agent`, `delay_seconds` and `decision` are all
      present, `paths_disallowed_used` is empty and `decision == "proceed"`;
      otherwise it refuses and names the failed condition. Proved by: test 9
      (one case per condition, plus the passing case) and a run of the
      installed `wordsworth-ingest` against a directory without `check.json`.

## 3b. Layout and hygiene (the reviewer's findings)
- [ ] `ingest_manifest_corpus`, `_advance` and the manifest logic in their own
      module; `src/wordsworth/ingest_corpus.py` keeps only CLI wiring; every
      file ≤200 lines. Proved by: `wc -l` on the touched files in the PR text,
      and the existing and new ingest tests still passing.
- [ ] No scratch or verification artefacts committed (no `.scratch-verify/`,
      no manifest, no `check.json`). Proved by: `git diff --stat main` in the PR
      text shows none.
- [ ] Extend, do not rename: every row of
      `docs/explanation/meting-woo-corpus-01.herkomst.jsonl` keeps `bestand`,
      `bron`, `opgehaald`, `besluit` and gains `file`, `url`, `fetched_at`.
      The fetch record stays additive. Restore the old keys if the earlier
      build renamed them. Proved by: the herkomst-sample test (task 4).

## 3c. Test correction (CI finding on PR #217)
- [ ] `test_openanonymiser_down_fails_the_run` asserts `rc == 1` and that
      nothing is indexed, not `State.EXTRACTED` (a failed anonymize leaves the
      document `REGISTERED`). Proved by: the test passing against a real
      Postgres (`WORDSWORTH_TEST_DATABASE_URL`) with the test not skipped, and
      CI's Fast test gate (offline) green.

## 4. Tests (`tests/test_ingest_corpus.py`, the design.md list)
- [ ] Tests 1 to 9 from `design.md`, integration through `ingest_corpus`.
      Database tests: use a private test database
      (`WORDSWORTH_TEST_DATABASE_URL`) and report which tests skipped.
- [ ] Herkomst-sample test (design test 8, no database needed): load
      `docs/explanation/meting-woo-corpus-01.herkomst.jsonl` through
      `wordsworth.eval.woo_collection.build()` and
      `wordsworth.dossier_tools.by_filename()`; assert every row maps (no
      `KeyError`, a non-empty mapping with one entry per row, no
      `zonder_herkomst`). Proved by: the test passing, and failing when the
      sample's `bestand` keys are removed.

## 5. Docs (must change with the code; CI fails on code without docs)
- [ ] `docs/reference/ingest.md`: the manifest format, the required
      `WORDSWORTH_BACKEND_ENV`, the read-back, and that
      a duplicate delivery keeps its first provenance and fails the run.
      Proved by: a docs review in the PR; the page names `--manifest`.
- [ ] `docs/reference/evaluation.md`, section "The published-dossier pilot":
      the gate order (check, then manifest, then ingest), `check.json` with its
      fields, and the layer rule. Proved by: a docs review in the PR.
- [ ] `docs/reference/cli.md`: the `wordsworth-ingest --manifest` option.

## 6. Verification
- [ ] Run the installed `wordsworth-ingest` from the side without the key:
      once with an unlisted file, once with `WORDSWORTH_BACKEND_ENV=alma` and
      once with it unset, and see all three refused. Ingest nothing from
      `~/wordsworth-pilot` (frozen). Proved by: the commands and output in the PR description.

## 3d. Architect finding (#221)
- [ ] The check's location and fields are fixed as above, not left to
      `pilot-report-template`. Proved by: test 9, and `docs/reference/ingest.md`
      listing the `check.json` fields and the refusal reasons.

## 7. Later, not this change
- Recording provenance on re-delivery (own OpenSpec change).
- `pilot-report-template`, the pilot ingest run itself, and the gold-set
  tooling.
