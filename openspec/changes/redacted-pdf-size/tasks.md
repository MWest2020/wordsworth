# Tasks

## 1. Measure
- [ ] Record the current bytes per page of a rendered fixture page and, from the
      cached `redacted/` object, the page count and size of 00213a91.
      Proved by: the figures in the PR description; the budget in section 3 is
      set from them.

## 2. Compress
- [ ] `pdf_render.render` stores the page rasters compressed (method chosen and
      measured by the builder, see the proposal's open questions); boxes are
      painted before encoding.
      Proved by: `tests/test_pdf_render.py` — the existing text-layer, box
      position, tesseract and nothing-carried-over tests still pass.
- [ ] The codec does not weaken the redaction.
      Proved by: a test that renders the output PDF with pdfium and asserts the
      pixels inside each rectangle are the box colour (within the codec's
      stated tolerance if lossy) and that tesseract finds no redacted name.

## 3. Test bytes per page
- [ ] A test renders a text page with a box and asserts bytes per page under a
      stated budget, far below the raw raster size of that page.
      Proved by: `tests/test_pdf_render.py::test_page_size_is_bounded` fails on
      the previous implementation and passes on the new one.
- [ ] The reveal path is also bounded.
      Proved by: the same test with an empty box list.

## 4. The real artefact
- [ ] After deploy, remove the cached 151 MB object of 00213a91, fetch
      `GET /documents/{id}/redacted.pdf` so the endpoint renders, and read the
      size of the served response; open the PDF and look at a page.
      Proved by: the size in the PR description is a few MB; boxes and labels
      are in place. No PII is read or quoted.

## 5. Docs
- [ ] `docs/how-to/pdf-redaction.md`, section "How it is built": replace "every
      page is rasterised at 300 dpi" with the chosen method and resolution, and
      state the bytes-per-page budget and that boxes are painted before
      encoding.
      Proved by: the section names the method and the budget the test enforces;
      `grep -n "300 dpi" docs/how-to/pdf-redaction.md` shows only what is still
      true.
