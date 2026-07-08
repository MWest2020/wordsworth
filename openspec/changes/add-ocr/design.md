# Design decisions — add-ocr

## Seam and flow

`OcrEngine` protocol: `ocr(pdf_bytes) -> str`. Local implementation (tesseract
with the Dutch model, via ocrmypdf or pytesseract). A test double returns fixed
text.

Recovery flow reuses the existing profiling metric: run OCR on an
`unprocessable_ocr` document, then apply the same characters-per-page threshold to
the OCR output. Above threshold → `extractable` (text flows into extract →
anonymize → index like any other document). Below → stays `unprocessable_ocr`.
OCR engine failure → loud error (transient/retryable), never a silent skip.

## Boundaries

- **Local only** — no cloud OCR. CPU is acceptable (nightly batch); throughput is
  measured and reported like the rest of the pipeline.
- OCR is opt-in and runs after the main pass, so it never delays the born-digital
  path (the "no OCR tuning before something is searchable" scoping rule).

## Not in scope

Layout reconstruction, table extraction, handwriting. Plain text recovery only.
