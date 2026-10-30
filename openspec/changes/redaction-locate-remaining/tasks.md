# Tasks

Tasks 1 and 2 are the build: offline, synthetic input, no deployed service.
Task 3 is an operator step outside the build. Task 4 is docs.

## 1. The invariant error (build)
- [x] The investigation uses only the safe features (`label`, `lengte`, `in_bron`,
      `na_vervanging`, `woorden`, `alnum`) or one added feature that is a count or
      class. Acceptance: if a feature is added, it is an integer or a fixed-
      vocabulary class and cannot identify anyone. Proved by: a test in
      `tests/` that builds the error from a synthetic surviving value and asserts
      the feature set contains no string taken from the text.
      Done by `test_masking_an_existing_token_can_expose_a_survivor`
      (`tests/test_pseudonymizer.py`): the six existing features already explain
      a survivor end to end (`in_bron`/`na_vervanging` show it was never in the
      source and masking created it) — no new feature was needed.
- [x] A test that when a detected value survives replacement the error
      `waarde-overleefde-vervanging` is raised and the text is never emitted.
      Acceptance: with a synthetic value that survives, the function returns no
      anonymised text; `str(error)`, `repr(error)`, its attributes and the audit
      record written for the failure do not contain the value or any substring of
      it longer than one character. Proved by: the test.
      Same test, driven through the real path (`ReversibleAnonymizer._pseudonymize_entities`):
      a pre-existing token masked to a fixed placeholder exposes a value that
      never literally occurred in the source — the mechanism measured on
      2026-09-14. Also covered end-to-end via the API in
      `tests/test_reversible_backfill_db.py::test_de_kenmerken_van_de_invariant_komen_in_de_audit`.
- [x] The error counts as `failed`, not `retryable`. Proved by: a test in
      `tests/test_reprocess_overslaan.py` that a document raising it is tallied
      under `failed`.
      Done by `test_een_gebroken_invariant_telt_als_failed_niet_retryable`.

## 2. Count-by-type report (build)
- [x] The report, as code, groups the `value-not-located` entries of a reprocess
      `problems` list by PII type. Acceptance: for each type it returns the
      number of documents and the located and in-text totals, and nothing else.
      Proved by: a test with synthetic `problems` covering at least three types
      and two documents in one type, asserting exact counts.
      Done by `wordsworth.value_not_located_report.by_type` and
      `tests/test_value_not_located_report.py::test_groups_by_type_with_exact_counts`
      (PERSON/LOCATION/EMAIL, two PERSON documents).
- [x] The report and the log lines of any new module hold only type, length and
      counts. Acceptance: with synthetic values and page text in the input, no
      output line, return value or captured log record contains them. Proved by:
      a test that scans the output and `caplog` for those strings.
      Done by `test_report_and_log_hold_no_value_or_page_text`.
- [x] A miss still fails closed. Proved by: a test that a document in the report
      has no redacted PDF served (409 or 404 as today on
      `GET /documents/{id}/redacted.pdf`).
      Done by `tests/test_reversible_backfill_db.py::test_a_value_not_located_miss_is_in_the_report_and_still_fails_closed`.

## 3. Run it live (operator, not part of the build)
Run by Mark or the odin coding session on the host. Not done by a builder.
- [ ] Precondition: confirm `pdf-redaction-match` is deployed (its task 3 is still
      unchecked in the archive). Acceptance: the running image contains that
      change. Proved by: a line in the wordsworth#261 comment naming the image
      tag or commit.
- [ ] Run `POST /reprocess` over the 415 documents on the deployed service (or
      `wordsworth reprocess --all`), with the API key and OpenBao token from SOPS
      or OpenBao, never in the PR, the repo or a log. Acceptance: the run
      finishes; the report from task 2 is produced from its `problems`. Proved
      by: the by-type counts compared with the 51 of #259.
- [ ] For the real invariant document, answer yes or no: is anonymised output
      outside the redacted PDF affected. Acceptance: the answer is derived from
      type, length and counts only. Proved by: the yes or no in the comment; on
      yes, Mark is told at once.
- [ ] Post the result as a count-only comment on wordsworth#261. Acceptance: it
      holds types, lengths and counts, no value, page text or context. Proved by:
      the comment itself.

## 4. Docs (must change with the code)
- [x] `docs/how-to/pdf-redaction.md`: the by-type report and the invariant error
      (code, what it carries, that it is not retried). Proved by: the section
      names both.
      Done: "## The count-by-type report" and "## When replacement itself
      survives: `AnonymizationInvariantError`".
- [x] `docs/how-to/reversible-backfill.md`: how the report is run, the access
      path and credentials for the live step, and what it reports (type, counts,
      no value). Proved by: the section names the counts and the access path.
      Done: "## Running the count-by-type report over a live run".
- [x] `openspec validate redaction-locate-remaining --strict` passes.
