# Design: synthetic-long-corpus

## Values

`bsn_test_range(rng)` and `iban_fake_bank(rng)` go **next to** `bsn` and `iban` in
`wordsworth.eval.synthetic`; the existing two stay unchanged, so the 500-document corpus
keeps its values and stays comparable with earlier measurements.

- `bsn_test_range`: the published test range is 999990000–999999999 (Logius). Fix the
  first five digits to 9 (they contribute 9·(9+8+7+6+5) = 315 to the weighted sum) and
  search the remaining four for an elfproef-valid number. `is_valid_bsn` checks the
  elfproef only and `_BSN_RE` is `\b\d{9}\b`, so these stay detectable.
- `iban_fake_bank`: the existing mod-97 construction with bank code `ZZZZ`, which no
  Dutch bank has. `is_valid_iban` checks mod-97 only, so it stays detectable.
- Fix the stale comment on `iban()`: it calls `INGB` a test bank code, and INGB is a
  real bank.

## Layout (files ≤ 200 lines)

- `src/wordsworth/eval/long_corpus_parts.py`: the six part builders (cover, table of
  contents, letter, e-mail thread, minutes, table), each returning a `Document` (text
  plus gold spans). A split to keep every file ≤ 200 lines, not new scope.
- `src/wordsworth/eval/long_corpus.py`: assembling pages from the parts; the per-page
  gold records; the queries with their planted answer.
- `src/wordsworth/eval/long_corpus_pdf.py`: writing the PDF and rasterising the scanned
  pages.
- `scripts/eval/generate_long_corpus.py`: a thin CLI that parses arguments and writes
  the files, the same shape `generate_ground_truth.py` has against `synthetic.py`.

## One Document per page

Each page is built as a `Document` of planted values (type and string). The page is
drawn (laid out with simple wrapping), then read back with `page_text` per page. For a
born-digital page the gold `text` IS that extracted text, and each gold offset is
computed by locating the planted value in it. The gate is that every planted value is
found exactly once; zero or two hits fail the generator, so each value is planted once
per page. Offsets are character offsets into the extracted text, which is the string the
detectors scan, so `load_gold`'s range check holds and "detections equal gold" is
offset-exact over extracted text. The drawn string is not the gold text. A scanned page
has no text layer; its `gold_scanned.jsonl` text is the text that was rasterised.

**Every planted value is drawn as one `drawString` run**, never split across a line
break, table columns or a justified gap. `page_text` inserts a virtual space where two
glyphs on a line are more than 0.4 character heights apart, and pdfium's reading order
across table columns is not the order of writing. A value split that way would not be
found on exactly the table pages. Table cells hold whole values, one per run.

## The extraction gate

The test that proves the gold true opens each generated PDF with pypdfium2 and calls
`wordsworth.pdf_text.page_text` **per page**, iterating pages as `profiling.py` does.
`positioned_text` joins pages and loses the boundary. Every gold value of a born-digital
page is found exactly once in that page's extracted text, and each gold offset slices
back to its value. Every scanned page must have an empty
text layer and no line in `gold.jsonl`.

## Scanned pages

The scanned set is drawn from the pages other than page 1 and the answer page, so the
planted answer always has a text layer; a gate test asserts it for every document.
The tests pass an explicit `--scanned` (for example 0.5 on `--docs 2 --pages 6`) and
assert that at least one scanned page exists: the default 0.1 rounds down to none on 6
pages, and the scanned-page assertions would pass vacuously.

**E-mail threads:** every From/To address is planted as gold, or is an address
`_EMAIL_RE` does not match; the detections-equal-gold test covers all four types
(BSN, IBAN, e-mail, postcode).

The pixels come from pdfium (pypdfium2, as `pdf_render.py` does): the chosen page is
rasterised at 200 dpi, encoded as JPEG (quality 80) by PIL and re-embedded as an
image-only PDF page of the same size, in place of the text page. JPEG, not raw pixels:
a flate-compressed bitmap is how a document once came out at 151 MB. Rejected: drawing
a raster on the reportlab canvas in one pass, because reportlab cannot rasterise its own
page, so the pixels would need another source anyway.

## Determinism

reportlab writes a wall-clock `/CreationDate` and a time-derived `/ID`. Build every
canvas with `Canvas(..., invariant=1)` and set Author, Title, Subject and Creator
explicitly. The reproducibility test asserts byte-identical output for the same seed,
and also that the embedded creation date is the invariant constant, not now: two
generations within one second would otherwise match by luck.

## Queries

The query text is the planted answer phrase verbatim; the manifest keeps it as
`answer_phrase`. The long-document ranking measurement is therefore a phrase lookup.
Rejected: a paraphrased or question-form query, which would mix semantic retrieval into
a length-fairness measurement.

## Headers and footers

The document number is `WOO-<year>-<4 digits>`, never 9 digits (about 1 in 11 nine-digit
numbers passes the elfproef and would count against precision on every page) and never
`\b[1-9][0-9]{3}\s?[A-Z]{2}\b` (the postcode shape). Letterheads use no postcode shapes
either, unless planted on purpose as gold.

## Size and time

30 × 30 pages of text through reportlab plus ~90 raster pages at 200 dpi takes minutes;
the raster pages dominate the size, well under 100 MB. The test suite uses `--docs 2
--pages 6`. A full-size corpus is never part of the suite.
