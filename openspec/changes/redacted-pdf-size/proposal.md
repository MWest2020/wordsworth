## Why

The redacted PDF of one document (00213a91, Gooise Meren dossier) is 151 MB.
The coding session, after fixing the zero-height boxes (#257): *"every page is
a 300 dpi raster, uncompressed. Compress it (JPEG/Flate, or a lower dpi for
text pages) to a few MB, with a test on bytes per page."* The decision in the
channel: *"Compress the redacted PDF (now 151 MB for one document, a raw 300 dpi
raster) to a few MB, with a test on bytes per page."*

`pdf_render.render` hands each page to reportlab as an RGB `PIL` image at
`DPI = 300`, and the output size follows the raw pixel count.

## What changes

- The redacted and reveal PDFs are built so that their size is bounded: a
  document that now takes 151 MB comes out at a few MB.
- A test measures bytes per page of a rendered PDF against a budget, so a later
  change that brings the raw raster back fails CI.
- The black boxes still cover the values, with the layout intact. The boxes are
  painted before the raster is encoded, as now.
- The `pdf-redaction` requirement "The redacted PDF has nothing under the box"
  is modified: it no longer fixes the raster at exactly 300 dpi, and it gains
  two scenarios (bounded size, compression does not weaken the redaction). Its
  four existing scenarios stay.
- `docs/how-to/pdf-redaction.md` ("How it is built") is updated.

## Open questions

- **Method:** JPEG, Flate, a lower dpi for text pages, or a combination. The
  channel named these and chose none. `design.md` states what the choice must
  preserve; the builder picks and measures, and records the choice in the docs.
- **The budget:** the bytes per page the test enforces. "A few MB" for 00213a91
  is the target; that document's page count and the per-page figure are not in
  the channel. The first task measures the artefact and the builder sets the
  figure.
- **Reveal:** `reveal.pdf` uses the same `render`, so it gets the same
  compression. Whether a reveal page may be encoded differently from a redacted
  one was not discussed; this change assumes no.
