# A truly redacted PDF as a core output

## Why

Mark, via the odin coding session: *"what we want is the anonymising in the
PDF."* Today the PDFs are read out completely and the layout is lost.
wordsworth extracts plain text with pypdf, anonymises that text, and stores and
shows only text. No positions on the page are kept and no PDF is ever written.
That was a deliberate choice: ADR-0005 D11 puts "re-rendering a docx/PDF with
placeholders" outside the core, in a separate render component.

The assignment from the orchestrator: anonymise inside the PDF, layout intact.
A redacted PDF per document where the text under each box is removed, not just
covered, with a typed label such as `[PERSOON 1]` on the box, and layout,
images and pages otherwise intact. With a reveal grant the same view shows the
originals; the original bytes never leave, as before.

This changes a promise (what a consumer can get out of the system and what a
redacted file guarantees), so it is an OpenSpec change, not an issue.

## What changes

A new capability `pdf-redaction`:

- **A box map** per document: for each redaction, the page, the rectangle and
  the token. It holds no values and is never persisted with values.
- **Locating**: inside `process` and `reanonymize`, each detected value is
  located whole-word in the positioned text of pypdfium2, never by character
  offsets from the pypdf text. If a value occurs fewer times in the positioned
  text than in the pypdf text, the run fails hard with a `value-not-located`
  audit record, and the endpoint answers 409 with no PDF.
- **Rendering**: every page is rasterised at 300 dpi, the rectangles are
  painted, and a new PDF is built with reportlab. Vector `[PERSOON n]` labels
  come from `legible.to_legible`. An invisible text layer carries the labels in
  place of the redacted spans. Nothing is copied from the source PDF: no
  metadata, no annotations, no outlines.
- **`GET /documents/{id}/redacted.pdf`**, cached under
  `redacted/<doc>/<boxmap_hash>`. It answers 409 `stale` when the current
  `lists_hash` differs from the one the box map was made with; `reanonymize`
  regenerates the box map.
- **`POST /documents/{id}/reveal.pdf`** with a grant draws clear values for the
  granted types only. It is never cached and is audited as a deanonymize with
  `view=pdf`.
- **OCR scans** use the existing ocrmypdf `object_key`, whose text layer is
  positioned.
- **ADR-0005 D11 is amended, narrowly**: a redacted rendering of the source PDF
  is a core output. Other formats (docx and the like) stay out.
- **Dependencies**: reportlab becomes a runtime dependency (it is dev-only
  today); pypdfium2 is added.
- **Backfill** of the 12 pilot documents and `gooise-meren-woo-2022` (567
  documents) via `reanonymize`.
- **Docs** that describe this behaviour change with it (see tasks.md).

## Non-goals

- Redaction of docx or any other format; D11 stays as it is for those.
- Keeping positions at extraction (word boxes stored per page). Positions are
  found at render time from the PDF instead; see design.md.
- A workflow or render service outside the API.

## Open questions

- **The console.** The assignment asked for the redacted PDF to be shown in the
  console, and for the reveal view to be reachable there. The decision recorded
  here covers the two endpoints only. Whether and how the console embeds them
  is not decided and is not a requirement in this change.
- **Licence of the new dependencies.** pypdfium2 (and the PDFium it bundles) and
  reportlab must be confirmed MIT-compatible before the build adds them
  (CLAUDE.md: MIT; no copyleft). The decision names both; the licence check is
  a task, not an assumption.
- **Whether tesseract is available in CI.** The raster test uses it; this
  change says the test skips visibly when it is absent, which is Mark's call to
  accept or to make mandatory.
