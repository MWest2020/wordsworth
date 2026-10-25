# Tasks

## 1. One extraction
- [ ] `positioned_text(pdf)` over pypdfium2, `text_source` `"pdfium-v1"`; used by
      profiling, detection, `DocumentText`, the index text and the box map.
      Proved by: test that a PDF is profiled, detected and boxed from the same
      text.
- [ ] Space insertion between characters further apart than a fixed fraction of
      the character height when pdfium emitted none; the inserted space has no
      char box. Proved by: test with a PDF whose words pdfium joins; the value is
      found whole-word and no box exists for the inserted space.
- [ ] A test PDF where pypdf joins table cells. Proved by: the test shows the
      pypdf text holds a value that is absent from the positioned text, and every
      value detected from the new extraction is located.

## 2. Count check
- [ ] Per token, count in the anonymised text must be at most the whole-word
      matches of its value in the positioned text, else `value-not-located` and
      409. Proved by: test with a token occurring twice in the anonymised text
      and its value once in the positioned text (the existing
      `test_value_not_located_writes_audit_and_persists_no_box_map` adapted).

## 3. Reprocess and backfill
- [ ] `POST /reprocess` puts every `value-not-located` in `problems`. Proved by:
      a test that goes through reprocess and asserts a non-empty `problems`.
- [ ] `text_source` on the anonymize and reanonymize audit record. Proved by:
      test reading the record.
- [ ] The backfill picks up every document without `pdfium-v1` and reports
      orphaned token counts. Proved by: test with one document recorded without
      `text_source` and one with `pdfium-v1`; only the first is picked up.

## 4. Hard gate
- [ ] Run detection over the pilot set plus `gooise-meren-woo-2022` with both
      sources and compare aggregate counts per type. Proved by: the gate report
      in the PR; a PERSON or BSN drop is a finding that blocks.

## 5. Acceptance on the deployed service
- [ ] Documents 4d58906e, 00213a91 and 006bb702 reprocessed. Proved by: the
      reprocess response with no `problems` entry for them.
- [ ] One `GET redacted.pdf` returns 200, and pypdf and pdfium both find no
      redacted value in its text layer. Proved by: the check run against the
      deployed service, output in the PR.

## 6. Docs (must change with the code)
- [ ] `docs/how-to/pdf-redaction.md`: the `value-not-located` section (one pdfium
      text, the count check wording). Proved by: no remaining claim there that
      detectors run over the pypdf text.
- [ ] `docs/how-to/reversible-backfill.md`: `text_source`, the pick-up of
      documents without `pdfium-v1`, orphaned token counts, `problems`. Proved
      by: the section names each.
- [ ] `docs/reference/architecture.md`: the extraction step names pdfium. Proved
      by: no stale pypdf extraction claim remains in the file.
- [ ] `openspec validate pdf-redaction-locate --strict` passes.
