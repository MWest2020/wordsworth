---
status: draft
last_reviewed: 2026-10-24
---

# Pilot report template

A report for the published-dossier pilot (`docs/reference/evaluation.md`,
"The published-dossier pilot") is a copy of this template with its fields
filled in. Two sections are Mark's alone: the ranking-gate slot and the
PII-gate slot. Nobody else fills those, and an empty slot is reported as
"not yet run" — never as passed, never as failed.

## 1. The check

Copied verbatim from the pilot's `check.json` (see `docs/reference/ingest.md`,
"`check.json` — the pilot's completed check"). Not re-described: `check.json`
stays the source and the ingest gate (`document-lifecycle`) stays as it is.

| field | value |
| --- | --- |
| `checked_by` | |
| `checked_at` | |
| `robots_txt` | |
| `anubis` | |
| `decision` | |

## 2. The corpus

| field | value |
| --- | --- |
| number of documents | |
| number of pages | |
| pages without a text layer | |
| scans | |

With no scans in the corpus, the OCR recovery path (`unprocessable_ocr`) is
barely tested by this pilot.

## 3. The ranking-gate slot — Mark fills this, nobody else

The gate: the expected document in the top 8 for at least 4 of the 5
questions below, gating this pilot run only.

The questions and their expected documents are committed *before* any result
is seen; the two timestamps below are the only way to read that order off the
report afterwards.

- Questions committed at:
- Time of the first search:

| # | question | expected document | document found in top 8? |
| --- | --- | --- | --- |
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

**Outcome:** not yet run.

## 4. The PII-gate slot — Mark fills this, nobody else

Mark's read of the anonymized text of every pilot document against the
source. Any leftover direct identifier of a private person (name, address,
e-mail, phone, BSN, IBAN) fails the pilot for that document, unless the
document is excluded below with the reason written down.

Published material is already redacted by the municipality before wordsworth
ever sees it; there is no unredacted original to measure what wordsworth
would have missed. This report and this template make no claim about that —
anonymization of *unpublished* documents remains unproven by this pilot.

| document | leftover identifier found | excluded (reason) |
| --- | --- | --- |
| | | |

**Outcome:** not yet run.

## 5. Findings so far

- The 567-document dossier `gooise-meren-woo-2022` has unknown provenance.
- Provenance is not recorded when a document is delivered again: a duplicate
  keeps its first recorded provenance and fails the manifest run (see
  `docs/reference/ingest.md`, "Read-back: the proof, not a re-run"). Neither
  finding is fixed by this pilot or this report.
