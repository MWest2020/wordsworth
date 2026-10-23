# Tasks

## 1. Manifest format and parsing
- [ ] Define the shared record (`url`, `fetched_at`, `sha256` per file) and a
      reader/writer used by both the fetcher and `ingest_corpus.py`.
      Proved by: test 2 (a record written as the fetcher writes it is ingested).
- [ ] `fetch_woo_corpus.py` writes the shared record. Proved by: test 2.

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
- [ ] Missing or non-homelab backend refused, alma included (the mechanism is
      the open question in `proposal.md`; settle it before this task). Proved
      by: test 6.
- [ ] A layer that did not run fails the run, OpenAnonymiser down included.
      Proved by: test 7.
- [ ] A manifest whose pilot report lacks a completed check (who, when, quoted
      robots.txt and terms, Anubis status, decision `proceed`) is refused.
      Proved by: test 8.

## 4. Tests (`tests/test_ingest_corpus.py`, the design.md list)
- [ ] Tests 1 to 8 from `design.md`, integration through `ingest_corpus`.
      Database tests: use a private test database
      (`WORDSWORTH_TEST_DATABASE_URL`) and report which tests skipped.

## 5. Docs (must change with the code; CI fails on code without docs)
- [ ] `docs/reference/ingest.md`: the manifest format, the read-back, and that
      a duplicate delivery keeps its first provenance and fails the run.
      Proved by: a docs review in the PR; the page names `--manifest`.
- [ ] `docs/reference/evaluation.md`, section "The published-dossier pilot":
      the gate order (check, then manifest, then ingest) and the layer rule.
- [ ] `docs/reference/cli.md`: the `wordsworth-ingest --manifest` option.

## 6. Verification
- [ ] Run the installed `wordsworth-ingest` from the side without the key:
      once with an unlisted file, once with a non-homelab backend, and see both
      refused. Proved by: the commands and output in the PR description.

## 7. Later, not this change
- Recording provenance on re-delivery (own OpenSpec change).
- `pilot-report-template`, the pilot ingest run itself, and the gold-set
  tooling.
