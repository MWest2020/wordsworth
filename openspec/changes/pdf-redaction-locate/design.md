# Design

## One text, by construction

Detection finds values in a text; locating finds them again in the page's
positioned text. With two extractors the second search can miss what the first
found. If detection runs over the positioned text itself, every detected value
exists in it, so locating cannot fail for lack of text.

`positioned_text(pdf)` over pypdfium2 is the single PDF extraction, with
`text_source` `"pdfium-v1"`. Profiling, detection, `DocumentText`, the index and
the box map all read it. An OCR'd scan uses the same function on its ocrmypdf
`object_key`.

## Spacing

pdfium emits no space between some words. A space is inserted where two
characters on the same line are further apart than a fixed fraction of the
character height and pdfium emitted none. The inserted space has no char box, so
no rectangle is drawn for it on its own.

## The count check

Per token: count in the anonymised text must be at most the whole-word matches of
its value in the positioned text. Otherwise `value-not-located` and 409.

## Recording and backfill

The anonymize and reanonymize audit record gets `text_source`. The backfill
selects every document without `pdfium-v1`, re-derives it, and reports orphaned
token counts. Values are never reported.

## Rejected alternatives

- **`\s*` in pdf_boxes.py only**: fixes (a), not (b).
- **Fuzzy or per-word locating**: an approximate match can leave part of a value
  unredacted; the failure must stay hard.
- **pypdf layout mode**: still a second text with different whitespace.
- **A union of both texts**: two truths for one document.
- **Skipping (b) values as false positives**: they are detections; skipping
  would leave them out of the redaction.

## Risk and gate

Changing the text source changes what the detectors see. Detection is run over
the pilot set plus `gooise-meren-woo-2022` with both sources and aggregate counts
per type compared. A PERSON or BSN drop is a finding that blocks.

This is not an ADR-0005 amendment.
