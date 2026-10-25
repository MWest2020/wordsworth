---
status: draft
last_reviewed: 2026-10-25
---

# Runbook: the redacted PDF

`GET /documents/{id}/redacted.pdf` and `POST /documents/{id}/reveal.pdf`
return the document as a PDF with layout, images and pages intact, but with
every detected value removed from the page — not just covered — and a typed
label (`[PERSOON 1]`) painted on its box. ADR-0005 D11 is amended narrowly for
this: a redacted rendering of the source PDF is a core output; other formats
(docx and the like) stay out.

## Preconditions

Only in **reversible mode** (`WORDSWORTH_REVERSIBLE=true`, a key provider and
mapping store configured): the box map is built by transiently decrypting the
document's own pseudonyms to locate them in the PDF, so a document anonymised
with the irreversible driver — which keeps no mapping — has nothing to locate
and never gets a box map. `GET .../redacted.pdf` then answers 409.

## Get the redacted PDF

```sh
curl $API/documents/<doc>/redacted.pdf -o redacted.pdf
```

Cached under `redacted/<doc>/<boxmap_hash>` in object storage — a second call
reads the cached object rather than re-rendering. Responses:

| Status | Meaning |
|---|---|
| 200 | the redacted PDF |
| 404 | unknown document |
| 409 `"no box map yet..."` | not processed in reversible mode, or the last run hit `value-not-located` |
| 409 `"stale"` | the current detection lists differ from the ones the box map was made under |

A `stale` response means the lists moved (git change, redeploy) since this
document's box map was built — not necessarily that the document itself is
behind. `reanonymize` (see [reversible backfill](reversible-backfill.md) and
[detection lists](detection-lists.md)) rebuilds the box map under the current
lists; the next call then serves a fresh PDF.

## Reveal a granted type, as a PDF

```sh
curl -XPOST $API/documents/<doc>/reveal.pdf -H 'content-type: application/json' \
  -d '{"grant_id":"<grant_id>","types":["PERSON"]}' -o reveal.pdf
```

The same grant and the same gates as [`/reveal`](grants.md) — a document that
has no box map yet also answers 409 here. The granted type is drawn in clear,
straight from the original page (nothing is decrypted to render it: the box
for that type is simply left unpainted, so the original pixels and the
original invisible text pass through); every other type keeps its box and
label. The result is **never cached or stored** — a cached reveal would be a
store of clear PII — and is audited exactly like `/reveal`: a `deanonymize`
record with `view: "pdf"`, the resolved types, and no clear value.

## The `value-not-located` audit record

Detection, profiling, the index text and the box map all read the **one** PDF
extraction (`positioned_text`, pypdfium2, `text_source` `pdfium-v1`,
pdf-redaction-locate) — pypdf is not used to extract PDF text any more. A
space is inserted where pdfium itself emits none between two characters that
sit far enough apart on a line; the inserted space has no character box, so
nothing is drawn for it.

A value is located **whole-word** in that positioned text. A line break acts
as a word separator (each run of it becomes one such space), so the last
word of a line is never glued to the first word of the next; a value's own
words are matched with optional whitespace between them, so a value detected
across a line break — carrying a literal break of its own — still matches.
Matching otherwise follows the value's normalisation rule
(pdf-redaction-match): case-insensitive for the casefold types (PERSON,
ORGANIZATION, LOCATION, EMAIL), whitespace-insensitive for POSTCODE, and
exact for every other type.

The count check: a token's count in the anonymised text must be at most the
whole-word match count of its value in the positioned text. When it is not,
the run writes a `value-not-located` audit record (the PII type and the two
counts, never the value) and persists no box map — a partly-redacted PDF is
never produced. The endpoint then answers 409 until a later run (after a
text/lists change) locates it. `POST /reprocess` (see
[reversible backfill](reversible-backfill.md)) lists every `value-not-located`
outcome it hits in its `problems` response, by document, PII type and the
counts (`located of in-text`, e.g. `0 of 1 located`).

## Character boxes: tight, or loose when tight is empty

Every box comes from `pdf_text.char_box`: pdfium's tight character box, or
its loose box (the font's full bounds) when the tight one is degenerate.
The Word-exported PDFs of the Gooise Meren Woo dossier report a tight box
0.01 pt high for every character (2026-10-26). Box maps built from those
covered nothing, and the first "redacted" PDFs showed every name; those
cached renders were deleted the same day.

The render refuses a box with no surface (`DegenerateBoxError`); the two
PDF endpoints answer 409 `"box map unusable ..."` until `reanonymize`
rebuilds the box map with real boxes. A redacted PDF that hides nothing is
never served.

## How it is built

Every page is rasterised at 300 dpi; the rectangles are painted into the
raster, so the text underneath is genuinely gone, not covered. The PDF is
then rebuilt from scratch with reportlab: vector `[PERSOON 1]`-style labels on
the boxes (`legible.to_legible`'s numbering — the same as
`?view=legible` on `/documents/{id}/anonymized`) plus an invisible text layer
for everything that is *not* redacted, so search and copy keep working for
the rest of the page. Nothing is copied from the source document: no
metadata, no annotations, no outline.

Scanned documents use the existing OCR text layer
(`object_key` repointed by the OCR recovery step) — there is no separate OCR
path for redaction.

## Not decided here

Whether and how the console embeds these two views is a separate, undecided
question (see the `pdf-redaction` proposal's open questions) — this runbook
covers the two HTTP endpoints only.
