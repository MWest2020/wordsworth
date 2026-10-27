# Tasks

## 1. The invariant error (first)
- [ ] Identify the document, the type and the cause of the
      `waarde-overleefde-vervanging` error from the safe features and, if
      needed, one added feature that is a count or class. Proved by: a
      count-only report in the PR naming type, lengths and counts, containing no
      value.
- [ ] State whether anonymised output outside the redacted PDF is affected.
      Proved by: the report says yes or no; on yes, Mark is told at once.
- [ ] A test with a text that reproduces the cause: replacement leaves no
      detected value, or the error is still raised and the text is not emitted.
      Proved by: the test, built after the cause is named.

## 2. Per-type diagnostic
- [ ] A count-only diagnostic over the value-not-located documents, per
      document and PII type: counts and a closed-vocabulary cause class.
      Proved by: a test that the output holds no value and no page text, and
      that it covers all six types.
- [ ] Run it on the deployed service, including 4d58906e (ORGANIZATION, 1 in
      text, 0 located). Proved by: the report in the PR, counts per type and
      cause.

## 3. Fixes
- [ ] One fix per named cause, each with a test that a document with that cause
      is located. Proved by: a test per cause; tasks are added here when the
      diagnostic names the causes.
- [ ] The count check still refuses: a token occurring twice with one match
      writes `value-not-located` and 409. Proved by: the existing
      `test_value_not_located_writes_audit_and_persists_no_box_map` stays green.

## 4. Flat boxes
- [ ] `reanonymize` the two documents with flat boxes. Proved by: `GET
      redacted.pdf` answers 200 for both and no box has zero surface.

## 5. Acceptance
- [ ] `POST /reprocess` over the 51 documents: the remaining `problems` are
      listed by type and counts. Proved by: the response in the PR.

## 6. Docs (must change with the code)
- [ ] `docs/how-to/pdf-redaction.md`: the causes found, the diagnostic, the
      flat-box 409 and its rebuild. Proved by: the section names each cause.
- [ ] `docs/how-to/reversible-backfill.md`: how the diagnostic is run and what
      it reports. Proved by: the section names the counts it reports.
- [ ] `openspec validate redaction-locate-remaining --strict` passes.
