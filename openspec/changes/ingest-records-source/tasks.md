# Tasks

## 1. Provenance at ingest
- [ ] Migration: `source_url`, `fetched_at` and `source_sha256` on the
      document, all nullable. The init-job carries the migration; api and
      init-job ship on the same digest.
- [ ] `/ingest`: the optional `source_url` and `fetched_at` parameters,
      validated as in design.md; 400 with the reason on bad input.
- [ ] The pipeline records `source_sha256` (from the bytes) and the two
      fields on the document and in the ingest audit record.
- [ ] Tests 1 to 3 from design.md (integration through `/ingest`).

## 2. No text layer is visible
- [ ] Test 4 from design.md. If today's behaviour indexes an empty text,
      fix it so that the document ends in a visible error state.

## 3. Docs
- [ ] `docs/reference/`: the ingest parameters and what is recorded.
- [ ] `docs/reference/evaluation.md`: the pilot definition and its gates, as
      in design.md, including "no recall claim from published material".

## 4. Later, not this change
- The pilot run itself: fetch the dossier by hand, write the questions,
  read the anonymised texts. It needs people and a publication choice.
- `municipal-eval-collection`, `egress-policy`, the new detectors, and the
  unpublished-documents gold set.
