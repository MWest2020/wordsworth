## Context

`pdf_render.render` rasterises each page at `DPI = 300`, paints boxes into the
PIL image, and passes it to `canvas.drawImage`. The output is built fresh, so
its size is dominated by the page images. 151 MB for one document is the raw
raster.

## Choices

- **One function, one fix.** `render` serves both endpoints; the fix goes
  there, so redacted and reveal PDFs both shrink. No second code path.
- **Paint first, encode after.** The boxes are painted into the raster before
  any encoding. Whatever codec is used only sees pixels that already have the
  box colour, so "nothing under the box" holds by construction.
- **What the method must preserve**, whichever the builder picks:
  - the pixels inside a box are still the box colour when the output is
    rendered again (a lossy codec must not break that scenario);
  - tesseract on the rendered page still finds no redacted value;
  - the page stays legible to a reader, which is the point of the PDF, so the
    resolution is not lowered past that;
  - labels stay vector text and the invisible text layer is unchanged;
  - the encoder adds no metadata, annotations or outlines.
- **Test on bytes per page, not total size.** A total depends on how many pages
  the fixture has; bytes per page is stable and catches the regression this
  change is about. The test also compares against the raw raster size of the
  page, so it cannot pass because the fixture is tiny.
- **Measure the artefact.** The final check reads the PDF the endpoint serves
  for 00213a91, not a re-render in a test harness.

## Rejected alternatives

- **Vector redaction instead of a raster** (strip text from the content stream,
  keep vector text). The clever pitfall: text can survive in fonts, ToUnicode
  maps and stray objects. The raster is the guarantee that nothing is under the
  box; it stays.
- **Refuse large documents.** Hides the problem.
- **Compress only when caching under `redacted/`.** Reveal is never cached and
  would stay huge, and cached and served bytes would differ.
