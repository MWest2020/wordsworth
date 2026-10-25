# Tasks

## 1. Locate
- [x] `_flatten` replaces each run of `\r`/`\n` with one space with rect `None`.
      Proved by: a test in `tests/test_pdf_boxes.py` with a value at the end of a
      line (`2022` then `Gemeente`) that is located, with no box for the space.
- [x] A value's words are matched with `\s*` between them. Proved by: a test in
      `tests/test_pdf_boxes.py` with a value that spans a line break, giving one
      rectangle per line.
- [x] Casefold types match case-insensitively, POSTCODE whitespace-insensitively,
      other types unchanged. Proved by: tests in `tests/test_pdf_boxes.py` for a
      PERSON stored in a different case than the page, a POSTCODE spaced
      differently, and a type outside the rule (still exact).

## 2. Reprocess message
- [x] The `value-not-located` problems message reads `located of in-text`. Proved
      by: a test in `tests/test_reprocess_overslaan.py` that a token with 1 in
      the text and 0 located reads "0 of 1 located".

## 3. Real artefact
- [ ] Reprocess 4d58906e, 00213a91 and 006bb702; each returns 200 on
      `GET /documents/{id}/redacted.pdf`. Proved by: the HTTP status per
      document, shown in the PR.
      BLOCKED: this builder's sandbox is an isolated repo clone with no
      network path to the deployed pod/database that holds these three
      documents (no kubeconfig, no `WORDSWORTH_API_URL` pointed at a live
      cluster). Needs to be run from where pdf-redaction-locate was deployed.

## 4. Docs
- [x] `docs/how-to/pdf-redaction.md` (section "The `value-not-located` audit
      record"): line breaks, `\s*` between words, and the per-type matching rule.
- [x] `docs/how-to/reversible-backfill.md` (the `problems` paragraph): counts read
      `located of in-text`.
- [x] `openspec validate pdf-redaction-match --strict` passes.
