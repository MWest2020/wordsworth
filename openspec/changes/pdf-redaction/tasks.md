# Tasks

## 1. Box map
- [ ] Compute the box map (page, rect, token; no values) inside `process` and
      `reanonymize`, locating each value whole-word in pypdfium2 positioned
      text. Proved by: test that a known name in a test PDF gets rects whose
      page matches, and that the box map serialised to storage contains no
      detected value.
- [ ] A two-line name gives two rects. Proved by: test with a name broken over
      two lines.
- [ ] Fewer matches than occurrences in the pypdf text writes a
      `value-not-located` audit record and no PDF. Proved by: test with a value
      that pypdfium2 cannot locate; audit record present, endpoint 409.

## 2. Render
- [ ] Rasterise at 300 dpi, paint rects, rebuild with reportlab; add vector
      labels from `legible.to_legible` and the invisible text layer with labels
      in place of redacted spans. Proved by: tests below.
- [ ] Name and BSN are gone from the text layer. Proved by: test extracting
      with pypdf and with pdfium and finding neither.
- [ ] Character boxes of the original lie inside the rects. Proved by: test.
- [ ] Pixels under the rects are the box colour. Proved by: test sampling the
      rendered page.
- [ ] The label is placed on its box. Proved by: test on the label position.
- [ ] No metadata, annotations or outlines are carried over. Proved by: test on
      the output PDF's info, annots and outline.
- [ ] Tesseract finds no name in the raster. Proved by: test running tesseract
      on the rendered page; skips visibly when tesseract is absent.
- [ ] OCR scan uses the existing ocrmypdf `object_key`. Proved by: OCR fixture
      test.

## 3. Endpoints
- [ ] `GET /documents/{id}/redacted.pdf` cached under
      `redacted/<doc>/<boxmap_hash>`. Proved by: test that a second call reads
      the cached object.
- [ ] 409 `stale` when `lists_hash` differs; `reanonymize` regenerates. Proved
      by: seam test of lists change, then 409, then reanonymize, then 200.
- [ ] `POST /documents/{id}/reveal.pdf` draws clear values for granted types
      only, is never cached, and is audited as deanonymize `view=pdf` with no
      clear value. Proved by: reveal-and-audit test, including an ungranted type
      staying labelled and no object written under `redacted/`.

## 4. Dependencies
- [ ] Move reportlab from the dev group to runtime dependencies and add
      pypdfium2, with `uv`. Proved by: `uv sync` without dev installs both;
      their licences checked for MIT-compatibility and recorded in the PR.

## 5. Docs (must change with the code)
- [ ] `docs/explanation/adr/0005-nora-target-architecture-alignment.md`: amend
      D11 narrowly. Proved by: docs review; D11 says PDFs are core, other
      formats out.
- [ ] `docs/how-to/reversible-backfill.md`: backfill via `reanonymize`. Proved
      by: docs review.
- [ ] `docs/how-to/detection-lists.md` ("Het bestaande corpus bijwerken"): a
      lists change makes the redacted PDF stale until `reanonymize`. Proved by:
      docs review.
- [ ] `docs/how-to/grants.md` ("Use a grant to reveal"): `reveal.pdf`. Proved
      by: docs review.
- [ ] `docs/how-to/console.md`: only if the open question on the console is
      decided; otherwise unchanged.
- [ ] `docs/index.md`: link the new how-to. Proved by: the link resolves.
- [ ] A how-to for the two endpoints, the 409 cases, and the `value-not-located`
      audit record. Proved by: docs review.

## 6. Backfill
- [ ] Run `reanonymize` over the 12 pilot documents and `gooise-meren-woo-2022`
      (567 documents). Proved by: a count of box maps equal to the document
      count, and the list of any `value-not-located` documents reported, not
      hidden.

## 7. Verification
- [ ] `openspec validate pdf-redaction --strict` passes. Proved by: the
      command's output.
