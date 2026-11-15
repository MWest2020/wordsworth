# Tasks

Tests use `lezer` (on the corpus-read list) and `derde` (logged in, on no
list), as in `api-corpus-read-gate`. A "deleted document" in a test is
deleted through `DELETE /documents/{id}` on a processed document, with the
Postgres stores, not a hand-written audit record. Every refusal is compared
on status and body.

## 1. The check

- [ ] 1.1 A helper (proposed `src/wordsworth/document_gone.py`, under 200
      lines) that takes a session and a document id, raises 404 `unknown
      document` when there is no state and 410 `document deleted` when the
      state is `State.DELETED`, and returns the state. It reads
      `pipeline.current_state` and nothing else. Proved by: unit tests for
      unknown, deleted, and each live state.
- [ ] 1.2 `document_anonymized`, `redacted_pdf` and `document_feedback` call
      it first in their body, after the declared gate; `redacted_pdf` loses
      its own 404 and 410 checks. Docstrings name the 410. `api.py` does not
      grow. Proved by: the tests in 2, `wc -l`, and
      `grep -n '"document deleted"' src/wordsworth/api.py` showing only the
      reveal route(s) that #494 has not yet moved, or none.
- [ ] 1.3 The reveal routes, `document_state`, `document_meta`,
      `delete_document_endpoint` and the console are not changed. Proved by:
      the diff.
- [ ] 1.4 `uv run ruff check src/ tests/` clean. Proved by: the output in the
      PR.

## 2. Tests: the content routes

- [ ] 2.1 Scenarios "The de-identified text of a deleted document", "The
      redacted PDF of a deleted document" (with a render put back under
      `redacted/<id>/` after the deletion) and "A deleted superseded copy"
      (body contains neither `superseded` nor the survivor's id). Proved by:
      the tests, and that the first fails against origin/main with 409.
- [ ] 2.2 Scenarios "Feedback after the deletion" and "Earlier feedback is
      kept": 410, record count of the document unchanged, `verify_chain`
      passes, the earlier `detection_feedback` records byte-equal. Proved by:
      the tests, and that the first fails against origin/main with 201.
- [ ] 2.3 Scenario "Feedback while the document is being deleted": the route
      decides under the lock `audit.append` takes. Two sessions against
      Postgres: the feedback request is held after it has taken the lock and
      the deletion is started; and the reverse order. In both, no
      `detection_feedback` record follows the `deleted` record, the state is
      `deleted` and the chain verifies. Proved by: the test, and that it fails with the state read
      moved back in front of the lock.
- [ ] 2.4 Scenario "A caller without corpus read learns nothing": `derde` on
      the three routes, for a deleted, a live and an unknown id: one 403, one
      body. Proved by: one parametrised test.
- [ ] 2.5 Scenarios "An unknown id is still unknown" and "A document that is
      not yet de-identified is not called deleted". Proved by: the tests.

## 3. Tests: the record routes and the list

- [ ] 3.1 Scenarios "The state of a deleted document" and "The trail of a
      deleted document": 200; the trail's last content-removing record is
      `deleted` with caller and counts; the serialised answer contains none
      of the document's seeded values, tokens or its filename. Proved by: the
      tests.
- [ ] 3.2 A table next to `tests/route_rows.py` with, for every route whose
      path contains `{document_id}`, its answer for a deleted document:
      `410`, `record`, `rerun`, `reveal-api` or `page` (design.md, decisions
      1 and 6). A test walks the application's routes (the collector of
      `tests/route_inventory.py`) and fails on such a route without a row and
      on a row without a route; it requests every `410` row (expects 410) and
      every `record` row (expects 200) as `lezer` against a deleted document.
      Proved by: the test, shown failing in the PR with a scratch
      `GET /documents/{document_id}/scratch` route and passing without it.
- [ ] 3.3 `DELETE /documents/{id}` on a deleted document answers as before
      (the `rerun` row). Proved by: the existing repeated-deletion tests
      unchanged and green.

## 4. Clients and docs

- [ ] 4.1 `wordsworth.client` and `static/console.js` do not treat the 410 as
      retryable or as success. Proved by: reading both for the three routes
      and a line in the PR saying what each does with a 410; a test in
      `tests/test_console_feedback.py` (or the JS test beside
      `test_console_pdf.js`) that a refused feedback shows "Niet opgeslagen
      (410)".
- [ ] 4.2 `docs/how-to/deleting-documents.md`: what each route answers after
      a deletion (the table of design.md, decision 1), and that the trail
      stays readable. Proved by: docs-gates green.

## 5. Check on the real service

- [ ] 5.1 In the demo harness, with the printed keys, as a program and as a
      browser: delete a document; as `mark` request the six routes of the
      proposal's table and paste the statuses; as `gast` request the three
      content routes for that id and for an unknown one (403 each). Proved
      by: the statuses in the PR.
- [ ] 5.2 If #501 is answered with the alternative before the build: replace
      the requirement "The record of a deleted document stays readable" by
      two rows in the 410 requirement, change the two `record` rows to `410`,
      and say so in the PR. If it is answered with the default or not at all,
      close it when this change is archived. Proved by: the issue's state.
- [ ] 5.3 `/security-review` on the diff, clean or every finding answered in
      the PR.
