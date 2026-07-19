## Why

The PoC parks scanned PDFs at `unprocessable_ocr` (a dead end). MVP needs OCR to
bring that portion of the corpus into the searchable set. Local OCR only — no
cloud in the critical path.

## What Changes

- Introduce an **`OcrEngine` protocol** (driver/protocol pattern) with a local
  engine (e.g. tesseract/ocrmypdf, Dutch language). No cloud.
- Add an **OCR recovery step**: an `unprocessable_ocr` document is run through OCR
  to produce text; if OCR yields usable text it becomes `extractable`, otherwise
  it stays `unprocessable_ocr`. OCR engine failure is a loud error, not a silent skip.

## Capabilities

### New Capabilities
- `ocr`: the OCR engine seam and the recovery of scanned documents into the
  extractable/searchable flow.

## Impact

- New dependency: a local OCR engine (tesseract + Dutch model / ocrmypdf).
- Adds an outgoing edge from `unprocessable_ocr` in the lifecycle; every
  transition remains an audit record. Does not touch `CLAUDE.md`, `.claude/agents/`, CI.
