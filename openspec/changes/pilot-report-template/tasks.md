# Tasks

## 1. The template
- [ ] Write the template with a section each for the check, the corpus, the
      ranking gate, the PII gate and the findings. Proved by: a read of the
      file against the design.md checks 1 to 3.
- [ ] The check section has fields for `checked_by`, `checked_at`,
      `robots_txt`, `anubis` and `decision`, taken from `check.json`. Proved
      by: the same read, and the field names matching `docs/reference/ingest.md`
      ("`check.json` — the pilot's completed check").
- [ ] The corpus section has fields for documents, pages, pages without a text
      layer and scans, and says that with no scans the OCR path is barely
      tested. Proved by: the read.
- [ ] The two gate slots are present, empty and marked as filled by Mark only.
      The ranking slot has 5 question rows with an expected document each, a
      questions-commit time and a first-search time. Proved by: the read, and
      a grep showing no question, timestamp or identifier is pre-filled.
- [ ] The findings section names the 567-document dossier
      `gooise-meren-woo-2022` with unknown provenance and the missing
      provenance on re-delivery. Proved by: the read.
- [ ] The word "recall" does not occur in the template. Proved by:
      `grep -ci recall` on the file returning 0.

## 2. Docs (CI fails on code without docs; this change has no code, but the
##    docs that describe the pilot must point at the template)
- [ ] `docs/reference/evaluation.md`, section "The published-dossier pilot":
      point at the template and state that the gate slots are Mark's. Proved
      by: a docs review in the PR; the section links the template.
- [ ] `docs/index.md`: link the template under `explanation/`. Proved by: the
      link resolves (the file exists at the linked path).

## 3. Verification
- [ ] `openspec validate pilot-report-template --strict` passes. Proved by:
      the command's output.

## 4. Later, not this change
- Mark's 5 questions and his PII read (he fills the slots in the report).
- Recording provenance on re-delivery (own OpenSpec change).
- The gold-set tooling.
