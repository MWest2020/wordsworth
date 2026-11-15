# Tasks

Built after `reveal-authorize-first` (#494) is built. Tests with caller
authentication on use `ontvanger` (the grant's recipient) and `derde`
(authenticated, not the recipient). "Stale" in a test means: the box map is
made, then the application is pointed at detection lists with another hash
(the lists rewritten on disk, as `test_stale_lists_then_reanonymize` in
`tests/test_redacted_api.py` does for the redacted PDF), not a hand-edited
`lists_hash` column.

## 1. The check

- [ ] 1.1 The reveal PDF path decides the box map with
      `pdf_redaction.box_map_status(session, document_id, current_lists_hash())`
      in place of `session.get(BoxMap, ...)`: `NO_BOX_MAP` keeps today's 409,
      `STALE` answers 409 `stale`. In `reveal_gate.decide(..., pdf=True)`,
      directly after the "no box map" answer and before the route calls
      `deanonymize()`. Proved by: the tests in 2, and
      `grep -n "session.get(BoxMap" src/wordsworth/api.py src/wordsworth/reveal_gate.py`
      showing no line on the reveal path.
- [ ] 1.2 The `reveal_pdf` docstring names the `stale` answer. `api.py` does
      not grow; `reveal_gate.py` stays under 200 lines. Proved by: `wc -l` in
      the PR.
- [ ] 1.3 `uv run ruff check src/ tests/` clean. Proved by: the output in the
      PR.

## 2. Tests

- [ ] 2.1 Scenario "A lists change, then stale, then reanonymize": a document
      with an e-mail address and a name the first lists do not detect; box map
      under the first lists; lists changed to deny-list the name; `ontvanger`
      with a grant for `EMAIL` calls `reveal.pdf`: 409 `stale`, no PDF bytes.
      After `reanonymize`: 200, and the name is absent from the PDF's text
      layer while the e-mail address is present. Proved by: the test, and that
      it fails against the code before 1.1 (the first call answers 200 with
      the name in the text layer; paste that failure in the PR).
- [ ] 2.2 Scenario "A stale refusal reveals and records nothing": audit record
      count for the document equal before and after, `verify_chain` passes,
      and a key provider that counts calls was asked for no key. Proved by:
      the test.
- [ ] 2.3 Scenario "The same answer as the redacted PDF": one caller, one
      stale document, both routes: equal status and equal body. Proved by:
      the test.
- [ ] 2.4 Scenario "A caller the grant does not cover hears nothing about
      staleness": for an unknown grant id, a revoked, an expired, an
      other-document grant and `derde` with `ontvanger`'s grant, the answer on
      a stale document equals (status, body, content type) the answer on the
      same document with a current box map. Proved by: one parametrised test.
- [ ] 2.5 Scenarios "A current box map is served as before" and "The text
      reveal is not affected". Proved by: the existing
      `tests/test_reveal_pdf_api.py` unchanged and green, and one new test
      that `/reveal` answers 200 on the stale document of 2.1.
- [ ] 2.6 The order of answers for a covered caller on a document that is
      deleted, superseded, without a box map, stale: 410, 409 naming the
      survivor, 409 `no box map yet`, 409 `stale`. Proved by: one test with
      four documents.

## 3. Console and docs

- [ ] 3.1 The console's disabled "Onthul als PDF" button and the API now
      agree. Proved by: a test in `tests/test_console_pdf_views.py` that on a
      stale document the page shows the button disabled with the `stale`
      reason and a direct `POST .../reveal.pdf` with that grant answers 409
      `stale`.
- [ ] 3.2 `docs/` where the reveal PDF is described (`docs/how-to/pdf-redaction.md`,
      `docs/how-to/grants.md`, `docs/how-to/console.md`): the 409 `stale` answer and that
      `reanonymize` clears it. Proved by: docs-gates green.

## 4. Rollout

- [ ] 4.1 Before the deploy, read and report, changing nothing: how many
      documents have a box map whose `lists_hash` differs from the deployed
      lists, and how many of those have an active grant. Proved by: the
      numbers in the deploy PR. If the count is not zero, `reanonymize` runs
      for those documents first, or the PR says who accepted the 409s.
- [ ] 4.2 After the deploy, with the real service and a grant, from the
      recipient's side: `reveal.pdf` on a current document serves a PDF; on a
      document left stale on purpose in the demo harness it answers 409
      `stale`, and the console shows the reason. Proved by: the statuses in
      the deploy PR.
- [ ] 4.3 `/security-review` on the diff, clean or every finding answered in
      the PR.
