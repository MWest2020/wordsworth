# Design

## Where it lives

Inside the core, in `process` and `reanonymize`, behind the API. ADR-0005 D11
said rendered outputs are out of core. This change amends D11 narrowly: a
redacted rendering of the **source PDF** is a core output because the
guarantee ("the text under the box is gone") can only be given by the code that
knows the detections. Other formats stay out. The ADR text is amended, not
rewritten.

## Locating values: whole-word in positioned text, never by offsets

Detections carry character offsets into the pypdf text. pypdfium2 extracts
text in a different order and with different whitespace, so those offsets do not
map onto it. The box map is therefore computed by searching each detected
value, whole-word, in the pypdfium2 positioned text, and taking the character
boxes of every match. A multi-line value (a two-line name) gives one rectangle
per line.

**Fail-hard check.** For each value, the number of matches in the pypdfium2 text
must be at least the number of occurrences in the pypdf text. Fewer means the
value is somewhere we cannot box. The run then writes a `value-not-located`
audit record and the endpoint answers 409 with no PDF. A PDF with a name still
legible under a missing box is the worst outcome; a refusal is not. This is the
null-vector rule applied here: no silent fallback.

The box map holds page, rect and token. It holds no values and is never
persisted with values.

## Rendering: rasterise, paint, rebuild

Every page is rasterised at 300 dpi, the rectangles are painted in the raster,
and a new PDF is built with reportlab. Nothing is copied over from the source,
so there is no metadata, no annotation, no outline, no hidden object to carry
the text. Labels are vector text (`[PERSOON n]` from `legible.to_legible`).
Search and copy still work through an invisible text layer in which the labels
replace the redacted spans.

## Cache and staleness

`GET /documents/{id}/redacted.pdf` is cached under
`redacted/<doc>/<boxmap_hash>`. The box map records the `lists_hash` it was made
with. When the current `lists_hash` differs, the endpoint answers 409 `stale`
rather than serving a PDF made under old lists. `reanonymize` regenerates the
box map, after which the endpoint serves the new PDF.

## Reveal

`POST /documents/{id}/reveal.pdf` with a grant draws the clear values for the
granted types only; other types keep their label. The result is never cached
(a cache would be a store of clear PII) and is audited as a deanonymize with
`view=pdf`, carrying types and no clear value, as the existing reveal does.

## OCR

A scan has no text layer in the original. The existing OCR step already stores a
text-layer PDF under an `object_key`; its text is positioned, and the same
locating runs on it. No new OCR path.

## Rejected alternatives

- **Offsets mapped to boxes.** The pypdf and pypdfium2 texts differ; an offset
  that is off by a few characters boxes the wrong word and leaves the name
  uncovered. This is the clever pitfall of the change. Rejected for whole-word
  search plus a count check.
- **Store word boxes at extraction.** Extra state to keep consistent with
  `lists_hash` and with re-extraction, and it still needs the same matching.
  Rejected; positions are read at render time.
- **Draw rectangles over the original page (overlay).** The text stays in the
  file under the box, copyable and searchable. Rejected; that is covering, not
  redacting.
- **PyMuPDF.** AGPL; excluded by CLAUDE.md.
- **Separate render component (the D11 position).** Would need the detections
  and the original, so it would hold the same data the core holds. Rejected for
  PDFs only.
- **Caching the reveal PDF.** Would persist clear PII. Rejected.

## Risks

- Rasterising makes the output larger than the source and loses selectable
  original text; the invisible layer restores search, not fidelity of fonts.
- Words split across lines by hyphenation may not match whole-word; the count
  check turns that into a visible 409, not a leak.
