# Tasks

## 1. Provenance at ingest
- [x] Migration: `source_url`, `fetched_at` and `source_sha256` on the
      document, all nullable. The init-job carries the migration; api and
      init-job ship on the same digest.
- [x] `/ingest`: the optional `source_url` and `fetched_at` parameters,
      validated as in design.md; 400 with the reason on bad input.
- [x] The pipeline records `source_sha256` (from the bytes) and the two
      fields on the document and in the ingest audit record.
- [x] Tests 1 to 3 from design.md (integration through `/ingest`).

## 2. No text layer is visible
- [x] Test 4 from design.md. Already true of today's behaviour (OCR
      recovery leaves a document that still yields no text parked at
      `unprocessable_ocr`, and a resumed `process()` on that state is a
      no-op); the test pins it so a later change cannot regress it quietly.

## 3. Docs
- [x] `docs/reference/ingest.md`: the ingest parameters and what is recorded.
- [x] `docs/reference/evaluation.md`: the pilot definition and its gates, as
      in design.md, including "no recall claim from published material".

## 4. Later, not this change
- The pilot run itself: fetch the dossier by hand, write the questions,
  read the anonymised texts. It needs people and a publication choice.
- `municipal-eval-collection`, `egress-policy`, the new detectors, and the
  unpublished-documents gold set.
