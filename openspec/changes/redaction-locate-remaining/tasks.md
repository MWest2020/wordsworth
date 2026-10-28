# Tasks

## 1. The invariant error (first)
- [ ] Identify the document, the type and the cause of the
      `waarde-overleefde-vervanging` error from the safe features and, if
      needed, one added feature that is a count or class. Proved by: a
      count-only report in the PR naming type, lengths and counts, containing no
      value.
- [ ] State whether anonymised output outside the redacted PDF is affected.
      Proved by: the report says yes or no; on yes, Mark is told at once.
- [ ] A test that when a detected value survives replacement the error is
      raised and the text is never emitted, and that the error, its message and
      the audit record hold no value. Proved by: the test.

## 2. Count-only reprocess report (after `pdf-redaction-match`)
- [ ] Confirm `pdf-redaction-match` is deployed before measuring. Proved by:
      the running image in the PR containing that change.
- [ ] `POST /reprocess` over the 415 documents on the deployed service; list the
      remaining `problems` by PII type with document counts and located-of-
      occurrences counts. Proved by: the response, reduced to counts, in the PR,
      compared with the 51 of issue #259.
- [ ] A test that the report and the log lines of any new module hold only type,
      length and counts: no value, page text or context. Proved by: the test.

## 3. Docs (must change with the code)
- [ ] `docs/how-to/pdf-redaction.md`: the by-type report and the invariant error
      (code, what it carries, that it is not retried). Proved by: the section
      names both.
- [ ] `docs/how-to/reversible-backfill.md`: how the report is run and what it
      reports (type, counts, no value). Proved by: the section names the counts.
- [ ] `openspec validate redaction-locate-remaining --strict` passes.
