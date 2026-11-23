# Tasks

Tests with caller authentication on use API keys for `ontvanger` (the grant's
recipient) and `derde` (authenticated, not the recipient). Every refusal below
is asserted from the side that does not hold the grant (`derde`, or a grant
that does not apply), and compares the whole answer: status, body and content
type, not the status alone. "Both routes" means one parametrised test over
`/reveal` and `/reveal.pdf`.

## 1. The gate

- [x] 1.1 New module `src/wordsworth/reveal_gate.py` (under 200 lines) with
      the uniform refusal as one constant and one `decide(...)` used by both
      routes, in the order of design.md: grant lookup, `authorize()` with the
      grant's own domain; then state and domain, both read always (or in one
      query), also when the state is None, so an unknown id and a document in
      another domain cost the same reads; `authorize()` with the document's
      domain; the VC gate; only then 410 / 409 superseded / 409 box map (pdf
      only) / 409 not de-identified. The docstring says why `authorize()` is
      called twice. Proved by: the tests in 2 and 3, a test that the state
      and domain reads both run for an unknown id (statement listener), and
      `wc -l`.
- [x] 1.2 `reveal` and `reveal_pdf` in `api.py` call `decide` and lose their
      own grant, state, superseded and `deleted` checks; their docstrings
      describe the new answers. `grants.py` is not changed. Proved by: the
      diff (`git diff --stat src/wordsworth/grants.py` empty) and
      `grep -n '"unknown grant"\|reveal on that one' src/wordsworth/api.py`
      showing no line in the two reveal routes.
- [x] 1.3 `uv run ruff check src/ tests/` clean. Proved by: the output in the
      PR.

## 2. Tests: the grant decides first, one refusal

- [x] 2.1 Scenario "A grant that does not apply reads nothing about the
      document": an engine `before_cursor_execute` listener records every
      statement during the request; for an unknown grant id, a revoked, an
      expired, an other-document grant and (auth on) `derde`'s request, on
      both routes, no statement names `documents`, `audit_records`,
      `document_texts`, `document_pseudonyms`, `pii_mappings`, `box_maps`,
      `document_summaries` or `dossier_documents` (the table names in
      `models.py`). Proved by: the test, and that it fails against
      origin/main.
- [x] 2.2 Scenario "A grant bound to another domain is refused after the
      lookup": the recipient of a default-domain grant on a document in
      another domain gets the uniform refusal on both routes (extend
      `tests/test_domain_keys.py:85` with the body and `reveal.pdf`). And
      scenario "An unscoped grant from another domain hears nothing about
      deletion or supersession": an unscoped grant bound to domain A, once
      with `allow_global_grants=True` and once as a `beheerder` role grant
      (`roles.ADMIN`), used by its recipient on a deleted document and on a
      superseded document registered in domain B, on both routes: the
      uniform refusal every time, never 410 or 409. Grants in
      `PostgresGrantStore`, so the deletion runs as in production (an
      unscoped grant is not removed by it). Proved by: the test, and that it
      fails if the domain check is moved after the 410/409 checks.
- [x] 2.3 Scenario "An unknown document and a document outside the scope look
      alike": `derde` with `ontvanger`'s grant, unknown id against a live
      document, both routes: identical status and body. Proved by: the test.
- [x] 2.4 Scenario "A superseded document does not name its survivor": as
      `derde`, and with a grant scoped elsewhere, on a superseded copy, both
      routes: the uniform refusal, the survivor's id and "superseded" absent
      from the body. Proved by: the test.
- [x] 2.5 Scenario "A deleted document is not announced": on a deleted
      document, both routes, with `no-such-grant`, with the grant the
      deletion removed and as `derde`: the uniform refusal, not 410. The
      grants live in `PostgresGrantStore` (`grant_store_factory`): only that
      store loses the document's grants on deletion; `InMemoryGrantStore`
      keeps them and would test something else. Proved by: the test.
- [x] 2.6 Scenario "An unknown grant is not a 404": `tests/test_reveal_api.py`
      `test_unknown_grant_is_404` becomes the uniform refusal, on an
      existing and an unknown document, both routes. Proved by: the test.
- [x] 2.7 Scenario "A grant that would cover any document does not cover a
      missing one": with `allow_global_grants=True` and an unscoped grant,
      an unknown id answers the uniform refusal on both routes
      (`test_unknown_document_is_404` rewritten). Proved by: the test.
- [x] 2.8 Scenario "All causes give one answer": one parametrised test per
      route over the eight causes of the scenario, asserting that all
      answers equal the first one (status, body, content type); once with
      `accept: application/json` and once with `accept: text/html`, where
      the 403 page is compared with the document id removed from it. All
      eight requests come from one authenticated caller (the 403 page shows
      the caller's label, so two callers would differ for that reason
      alone), with grants issued to that caller so that each cause reaches
      its own check: a revoked, an expired and an other-document grant of
      his, an unknown grant id, his live grant on an unknown and on a
      superseded or deleted document; the other-recipient cause uses a grant
      issued to somebody else, presented by the same caller. Proved by: the
      test.

## 3. Tests: what a covered caller still hears

- [x] 3.1 Scenario "The recipient of a grant on a copy is told the survivor"
      (and document-lifecycle "Reveal on a copy"): the existing superseded
      test in `tests/test_reveal_api.py` stays green; the same for
      `reveal.pdf`. Proved by: the tests.
- [x] 3.2 Scenario "A covered caller is told the document is deleted": with
      `allow_global_grants=True` and an unscoped grant, and separately with a
      grant under the `beheerder` role (`roles.ADMIN`), a deleted document answers 410 on both
      routes and nothing is revealed (no `deanonymize` record). Proved by:
      the test.
- [x] 3.3 Scenario "A grant removed by the deletion no longer covers":
      `tests/test_delete_renders.py:96-99` ("410 whatever the grant") is
      rewritten: the removed grant and `no-such-grant` get the uniform
      refusal; `GET /documents/{id}/redacted.pdf` keeps its 410. The test
      keeps `grant_store_factory=PostgresGrantStore`, which is what removes
      the grant on deletion. Proved by: the test.
- [x] 3.4 Scenario "A covered caller is told the document is not yet
      de-identified": the recipient of a grant on a registered, unprocessed
      document gets 409 on `/reveal`. Proved by: the test.
- [x] 3.5 Scenarios "A revoked grant is refused" and "A caller who is not the
      recipient is refused": the existing tests in `test_reveal_api.py`,
      `test_reveal_pdf_api.py` and `test_reveal_recipient_binding.py` also
      assert the body `{"detail": "grant not applicable"}`. Proved by: the
      tests.
- [x] 3.6 Scenarios "Reveal is audited", "The recipient reveals normally",
      "Without caller authentication nothing changes" and document-lifecycle
      "A superseded document is asked for": the existing tests, unchanged
      and green. Proved by: the suite.
- [x] 3.7 Scenario document-lifecycle "Reveal on a copy by a caller the grant
      does not cover": covered by 2.4; the test names this scenario in its
      docstring. Proved by: the test.

- [x] 3.8 Scenario "A covered caller without a required credential hears
      nothing about the document": with a VC issuer key configured and
      `vc_required=True`, the grant's recipient without an `X-VC` header
      (and once with an invalid one) on a superseded and on a deleted
      document (a grant that survives the deletion), both routes: 403
      `vc rejected: ...`, never 409 or 410. Proved by: the test.

## 4. Tests: no trace of the cause

- [x] 4.1 Scenario "A refusal writes no audit record": for each cause in 2.8,
      both routes, the count of `audit_records` and of
      `key_lifecycle_events` is equal before and after, and the document
      chain verifies. Proved by: the test.
- [x] 4.2 Scenario "A refusal logs nothing about its cause": `caplog` at
      DEBUG on the root logger during an unknown, a superseded, a deleted and
      an out-of-scope request, both routes: no record contains the survivor
      id, "unknown", "superseded", "deleted" or the state name, and the
      records per case are equal once the document id is replaced by a
      placeholder. Proved by: the test.

## 5. Docs

- [x] 5.1 `docs/how-to/grants.md`: a section "A refusal says nothing" with the
      table of answers (uniform 403 for the uncovered caller; 410 / 409 for a
      covered one), why (#487, the shares), how an operator finds the cause
      (`GET /grants/{id}`, `GET /documents/{id}/state`), and the deploy note
      that clients expecting 404 `unknown grant` or `unknown document` from a
      reveal now get 403, and that the former recipient of a document-scoped
      grant gets 403 instead of 410 after the document is deleted (the
      deletion removed his grant); `last_reviewed` updated. Proved by: docs-gates
      green.
- [x] 5.2 `docs/how-to/pdf-redaction.md` (the reveal paragraph, "a deleted
      one 410") and `docs/how-to/deleting-documents.md` (the 410 paragraph):
      `reveal.pdf` answers 410 only to a covered caller, the uniform refusal
      to anyone else; `redacted.pdf` unchanged. Proved by: docs-gates green.
- [x] 5.3 `docs/how-to/api-auth.md`: the reveal bullet says the grant is
      decided before the document is looked up and that every refusal is the
      same 403. `docs/how-to/console.md:33`: check that "an unknown grant"
      does not point at the reveal routes; reword if it does. Proved by:
      docs-gates green.
- [x] 5.4 `CHANGELOG.md` under Unreleased / Security: reveal no longer tells
      an uncovered caller whether a document exists, is deleted or which
      copy survives it (#487). Proved by: the diff.

## 6. Check and rollout

- [ ] 6.1 Local demo (`tools/demo`), with the printed keys, as a program: as
      `gast` with `mark`'s grant id, `reveal` and `reveal.pdf` on an unknown
      id, a live document and a superseded or deleted one: the same 403 and
      body each time; as `mark` (the recipient) on a superseded copy: 409
      naming the survivor. Proved by: the statuses and bodies pasted in the
      PR.
- [ ] 6.2 `/security-review` on the diff, clean or every finding answered in
      the PR.
- [ ] 6.3 `share-recipient-read` (#439) and `console-share` (#440) are not
      deployed before this change is deployed and #487 is closed
      (`api-corpus-read-gate` task 6.4). Proved by: the order of the deploy
      PRs.
