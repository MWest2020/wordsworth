# Tasks

## 1. Manifest format and parsing
- [x] Define the shared record (`url`, `fetched_at`, `sha256` per file) and a
      reader/writer used by both the fetcher and `ingest_corpus.py`.
      Proved by: test 2 (a record written as the fetcher writes it is ingested).
      (`src/wordsworth/manifest.py`; the file-identifying key is `bestand`,
      not a new `filename` — see design.md "Settled".)
- [x] `fetch_woo_corpus.py` writes the shared record. Proved by: test 2.

## 2. `--manifest` in `ingest_corpus.py`
- [x] A `*.pdf` without an entry aborts the whole run before any ingest.
      Proved by: test 3 (green, offline).
- [x] sha256 of each file checked against its entry. Proved by: test 4 (green,
      offline).
- [x] `source_url` and the manifest's `fetched_at` passed to `ingest()`; the
      ingest time is never substituted. Proved by: test 1 (written; could not
      execute in this sandbox — see note below).
- [x] Read-back of the `register` audit record after each ingest; mismatch or
      absence fails that document with the reason and the exit status is
      non-zero. Proved by: tests 1 and 5 (same dossier and another dossier;
      written, see note below).

## 3. Guards
- [x] Missing or non-homelab backend refused, alma included (settled: a
      declared allow-list, `WORDSWORTH_HOMELAB_HOSTS`, checked against each
      configured backend URL's hostname — see design.md "Settled"). Proved
      by: test 6 (green, offline).
- [x] A layer that did not run fails the run, OpenAnonymiser down included.
      Proved by: test 7 (written; could not execute in this sandbox — see
      note below).
- [x] A manifest whose pilot report lacks a completed check (who, when, quoted
      robots.txt and terms, Anubis status, decision `proceed`) is refused.
      Proved by: test 8 (green, offline).

## 4. Tests (`tests/test_ingest_corpus.py`, the design.md list)
- [x] Tests 1 to 8 from `design.md`, integration through `ingest_corpus`.
      **Not fully proved green**: this sandbox has no `docker` binary and no
      `WORDSWORTH_TEST_DATABASE_URL`, so every DB-backed test in the whole
      suite errors at fixture setup (`FileNotFoundError: docker`), not only
      the new ones — confirmed against pre-existing tests
      (`test_pipeline_resilience.py`) on this same checkout. The 6 guard tests
      that run before any session is opened (tests 3, 4, 6 x2, 8 x2) are
      green. Tests 1, 2, 5 (x2) and 7, which need a real session, are written
      against the `session_factory`/`mem_store`/`mem_index`/`fake_embedder`
      fixtures already used by `test_ingest_records_source.py` and
      `test_pipeline_resilience.py`, but are unverified here. Run with
      `WORDSWORTH_TEST_DATABASE_URL` pointed at a reachable Postgres before
      merging.

## 5. Docs (must change with the code; CI fails on code without docs)
- [x] `docs/reference/ingest.md`: the manifest format, the read-back, and that
      a duplicate delivery keeps its first provenance and fails the run.
      Proved by: a docs review in the PR; the page names `--manifest`.
- [x] `docs/reference/evaluation.md`, section "The published-dossier pilot":
      the gate order (check, then manifest, then ingest) and the layer rule.
- [x] `docs/reference/cli.md`: the `wordsworth-ingest --manifest` option.

## 6. Verification
- [x] Run the installed `wordsworth-ingest` from the side without the key:
      once with an unlisted file, once with a non-homelab backend, and see both
      refused. Proved by: the commands and output in the PR description.

## 7. Later, not this change
- Recording provenance on re-delivery (own OpenSpec change).
- `pilot-report-template`, the pilot ingest run itself, and the gold-set
  tooling.
