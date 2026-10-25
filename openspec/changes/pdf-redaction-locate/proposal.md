# Locate every detected value: one PDF extraction, pdfium

## Why

The orchestrator, from the odin coding session: *"pdf-redaction is deployed, but
0 of 3 real documents get a redacted PDF."* Reprocessing three documents of the
'Gooise Meren Woo-publicatie 2022' dossier (4d58906e, 00213a91, 006bb702) each
wrote a `value-not-located` record for one DATE_TIME (`in_pypdf` 1,
`in_positioned` 0). There is no box map, so `GET redacted.pdf` answers 409.

A count-only diagnostic on the same PDFs found two causes:

- **(a)** pdfium has no space between the words of a value, so the value is
  found only when whitespace is ignored entirely (`\s*`, not `\s+`).
- **(b)** pypdf strings together text that is not contiguous on the page, for
  example a number and a month from different cells. The detected value then
  does not exist in the positioned text even when whitespace and punctuation are
  ignored.

A second bug: `POST /reprocess` returned `problems {}` although all three hit
`value-not-located`; `reversible-backfill.md` says those are reported in
`problems`.

The root is that detection runs over one text and locating over another. A
narrow `\s*` fix does not touch (b). The fix is to have one text.

This changes a promise (what the stored and indexed text of a PDF is made from,
and when a redacted PDF can be produced), so it is an OpenSpec change.

## What changes

- **One extraction for PDFs**: `positioned_text(pdf)` over pypdfium2, with
  `text_source` `"pdfium-v1"`. Profiling (born-digital detection), detection,
  `DocumentText`, the index text and the box map all use it. pypdf is no longer
  used to extract PDF text.
- **Spacing**: a space is inserted where two characters on one line are further
  apart than a fixed fraction of the character height and pdfium emitted none.
  An inserted space has no char box.
- **The count check** (`pdf-redaction`): per token, its count in the anonymised
  text must be at most the whole-word matches of its value in the positioned
  text; otherwise `value-not-located` and 409.
- **`POST /reprocess`** puts every `value-not-located` in `problems`.
- **`text_source`** is recorded on the anonymize and reanonymize audit record.
  The backfill picks up every document without `pdfium-v1` and reports
  orphaned token counts.
- **Hard gate**: detection is run over the pilot set plus `gooise-meren-woo-2022`
  with both sources and aggregate counts per type compared. A PERSON or BSN drop
  is a finding that blocks.
- Spec deltas on `document-lifecycle` (born-digital detection, text extraction,
  the anonymize record and backfill), `ocr` (the pypdf extraction path) and
  `pdf-redaction` (count check, reprocess problems).

This is not an ADR-0005 amendment. (The orchestrator's recommendation called it
one; the decision in the channel is that it is not.)

## Rejected

- The `\s*` fix only: it does not fix cause (b).
- Fuzzy or per-word locating.
- pypdf layout mode.
- A union of both texts.
- Skipping (b) values as false positives.

## Open questions

- The fixed fraction of character height for the inserted space is not decided;
  the build picks it and the hard gate checks it.

## Acceptance

- The gate report is in the PR.
- A test PDF where pypdf joins table cells.
- A reprocess test with a non-empty `problems`.
- Documents 4d58906e, 00213a91 and 006bb702 reprocessed.
- One `GET redacted.pdf` returns 200, with pypdf and pdfium both finding no
  redacted value in its text layer, measured on the deployed service.
