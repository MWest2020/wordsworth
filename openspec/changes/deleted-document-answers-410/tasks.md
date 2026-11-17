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
- [ ] 1.2 A lock primitive in `audit.py`: `lock_chain(session)`, which takes
      the same transaction-scoped advisory lock `append` takes
      (`pg_advisory_xact_lock` on `_CHAIN_LOCK_KEY`, `audit.py:42`), and
      `append` calls it instead of its own statement, so there is one
      spelling of the lock. Taking it twice in one transaction is harmless
      (the lock is re-entrant per session and released at commit or
      rollback), so a route that locks and then appends does not block
      itself. Proved by: a unit test that `lock_chain` followed by `append`
      in one session returns, and a two-session test that a second session's
      `lock_chain` waits until the first commits.
- [ ] 1.3 `document_anonymized` and `redacted_pdf` call the helper of 1.1
      first in their body, after the declared gate and after
      `document_anonymized`'s `view` check; `redacted_pdf` loses its own 404
      and 410 checks. Docstrings name the 410. Proved by: the tests in 2.
- [ ] 1.4 `document_feedback` is the exception to "the helper first": it
      calls `audit.lock_chain(session)` FIRST, then the helper of 1.1, then
      builds the payload and appends, all in the one transaction it commits.
      The state the record carries is the one the helper returned under the
      lock. The helper before the lock is today's bug in a new place
      (`api.py:776-787` reads the state, `audit.append` locks later, and the
      engine is READ COMMITTED, `db.py:70`): a deletion can commit in between.
      A comment at the call says so. On the 404 and the 410 the transaction
      ends without a write and the lock goes with it. Proved by: task 2.3,
      and a test that a refused feedback (404, 410) leaves no session holding
      the lock (a second session's `lock_chain` returns at once).
- [ ] 1.5 `api.py` does not grow. Proved by: `wc -l` in the PR. And
      `grep -n '"document deleted"' src/wordsworth/api.py`, whose expected
      output depends on which build lands first. If `reveal-authorize-first`
      (#494) is already built: no line (the string lives in
      `document_gone.py` and `reveal_gate.py`). If it is not: exactly one
      line, in `reveal_pdf`, which this change must not touch; #494's build
      then removes it (its task 1.2) and owns the grep ending empty. The PR
      says which case applied.
- [ ] 1.6 The reveal routes, `document_state`, `document_meta`,
      `delete_document_endpoint` and the console are not changed. Proved by:
      the diff.
- [ ] 1.7 `uv run ruff check src/ tests/` clean. Proved by: the output in the
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
      decides under the chain lock (tasks 1.2 and 1.4). Two sessions against
      Postgres: the feedback request is held after it has taken the lock and
      the deletion is started; and the reverse order. In both, no
      `detection_feedback` record follows the `deleted` record, the state is
      `deleted` and the chain verifies. Proved by: the test, and that it fails with the state read
      moved back in front of `lock_chain` (paste that failure in the PR).
- [ ] 2.4 Scenario "A caller without corpus read learns nothing": `derde` on
      the three routes, for a deleted, a live and an unknown id: one 403, one
      body. Proved by: one parametrised test.
- [ ] 2.5 Scenarios "An unknown id is still unknown", "A document that is
      not yet de-identified is not called deleted" and "A request that is not
      valid is refused as before" (`view=nonsense`: 400 for a deleted, a live
      and an unknown id; a malformed id: 422; a feedback body that fails
      validation: 422 for a deleted and a live id, nothing appended). Proved
      by: the tests.

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
