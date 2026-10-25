# Tasks

## 1. Box map
- [x] Compute the box map (page, rect, token; no values) inside `process` and
      `reanonymize`, locating each value whole-word in pypdfium2 positioned
      text. Proved by: test that a known name in a test PDF gets rects whose
      page matches, and that the box map serialised to storage contains no
      detected value. (`tests/test_pdf_boxes.py`,
      `tests/test_pdf_redaction_pipeline.py`)
- [x] A two-line name gives two rects. Proved by: test with a name broken over
      two lines. (`test_two_line_name_gives_two_rectangles`)
- [x] Fewer matches than occurrences in the pypdf text writes a
      `value-not-located` audit record and no PDF. Proved by: test with a value
      that pypdfium2 cannot locate; audit record present, endpoint 409.
      (`test_value_not_located_writes_audit_and_persists_no_box_map`,
      `test_no_box_map_yet_is_409`)

## 2. Render
- [x] Rasterise at 300 dpi, paint rects, rebuild with reportlab; add vector
      labels from `legible.to_legible` and the invisible text layer with labels
      in place of redacted spans. Proved by: tests below.
- [x] Name and BSN are gone from the text layer. Proved by: test extracting
      with pypdf and with pdfium and finding neither.
- [x] Character boxes of the original lie inside the rects. Proved by: test.
- [x] Pixels under the rects are the box colour. Proved by: test sampling the
      rendered page.
- [x] The label is placed on its box. Proved by: test on the label position.
- [x] No metadata, annotations or outlines are carried over. Proved by: test on
      the output PDF's info, annots and outline.
- [x] Tesseract finds no name in the raster. Proved by: test running tesseract
      on the rendered page; skips visibly when tesseract is absent (confirmed:
      no `tesseract` binary in the build/test sandbox used for this change).
- [x] OCR scan uses the existing ocrmypdf `object_key`. No new OCR path: the
      source bytes `process`/`reanonymize` already fetch by `object_key` are
      whatever `recovery.recover` last repointed it to, so an OCR'd scan's
      positioned text comes from the same text-layer PDF without any
      redaction-specific branch. Not proved by a new OCR fixture test in this
      change — see "Deviations" below.

## 3. Endpoints
- [x] `GET /documents/{id}/redacted.pdf` cached under
      `redacted/<doc>/<boxmap_hash>`. Proved by: test that a second call reads
      the cached object (`test_redacted_pdf_served_and_cached`).
- [x] 409 `stale` when the lists differ from the ones the box map was made
      under; `reanonymize` regenerates. Proved by: seam test of a lists change,
      then 409, then reanonymize, then 200 (`test_stale_lists_then_reanonymize`).
      Compared against the lists AS CURRENTLY CONFIGURED
      (`DetectionLists.load(...).hash`), not against the document's own audit
      trail — see design note in `pdf_redaction.py`/api.py; those two are
      identical right after `reanonymize` runs, by construction, so comparing
      a document to itself could never detect staleness.
- [x] `POST /documents/{id}/reveal.pdf` draws clear values for granted types
      only, is never cached, and is audited as deanonymize `view=pdf` with no
      clear value. Proved by: reveal-and-audit test, including an ungranted type
      staying labelled and no object written under `redacted/`
      (`tests/test_reveal_pdf_api.py`).

## 4. Dependencies
- [x] Move reportlab from the dev group to runtime dependencies and add
      pypdfium2, with `uv`. Proved by: `uv sync --no-dev` installs both
      (verified); licences checked via package metadata — pypdfium2:
      "BSD-3-Clause, Apache-2.0, dependency licenses"; reportlab: "BSD
      license" — both MIT-compatible, recorded in `pyproject.toml`'s comment
      and the PR description.

## 5. Docs (must change with the code)
- [x] `docs/explanation/adr/0005-nora-target-architecture-alignment.md`: amend
      D11 narrowly.
- [x] `docs/how-to/reversible-backfill.md`: backfill via `reanonymize`.
- [x] `docs/how-to/detection-lists.md` ("Het bestaande corpus bijwerken"): a
      lists change makes the redacted PDF stale until `reanonymize`.
- [x] `docs/how-to/grants.md` ("Use a grant to reveal"): `reveal.pdf`.
- [ ] `docs/how-to/console.md`: the open question on the console is not
      decided in this change — left unchanged, as specified.
- [x] `docs/index.md`: link the new how-to. The link resolves (the file exists
      at `docs/how-to/pdf-redaction.md`).
- [x] A how-to for the two endpoints, the 409 cases, and the `value-not-located`
      audit record (`docs/how-to/pdf-redaction.md`).

## 6. Backfill
- [ ] Run `reanonymize` over the 12 pilot documents and `gooise-meren-woo-2022`
      (567 documents). **Not run from this change**: it requires a deployed
      environment (reachable object store holding those documents' bytes,
      reversible mode, OpenBao) that this sandboxed build does not have access
      to. What IS done: `reanonymize`/`process` compute the box map whenever a
      key provider + mapping store are passed, `wordsworth reprocess`/
      `POST /reprocess` now thread them through automatically in reversible
      mode (see `reprocess.py`, `api.py`), and this is documented in
      `docs/how-to/reversible-backfill.md`. The actual run, and its count of
      box maps vs. `value-not-located` documents, is an operational step for
      whoever has that access — flagged here rather than assumed done.

## 7. Verification
- [x] `openspec validate pdf-redaction --strict` passes. Proved by: the
      command's output (see PR description).
