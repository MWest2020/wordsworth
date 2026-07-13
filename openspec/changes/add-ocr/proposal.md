## Why

The PoC parks scanned PDFs at `unprocessable_ocr` (a dead end). MVP needs OCR to
bring that portion of the corpus into the searchable set. Local OCR only — no
cloud in the critical path.

## What Changes

- Introduce an **`OcrEngine` protocol** (driver/protocol pattern) with a local
  engine (tesseract + Dutch model via **ocrmypdf**) that produces a **text-layer
  PDF**, not raw text — so the recovered doc reuses the existing `profile_pdf` and
  `extract_text` path unchanged. No cloud.
- Add an **OCR recovery step**: `unprocessable_ocr` becomes non-terminal (gains
  edges to `extractable`/`failed`). A scanned document is OCR'd; if the text-layer
  PDF clears the threshold its bytes replace the stored bytes and it becomes
  `extractable`, otherwise it stays `unprocessable_ocr`. Every OCR attempt is
  audited (even a non-recovering one). OCR engine failure is a loud error, not a
  silent skip.

## Capabilities

### New Capabilities
- `ocr`: the OCR engine seam and the recovery of scanned documents into the
  extractable/searchable flow.

## Impact

- New dependency: a local OCR engine (ocrmypdf + tesseract + Dutch model).
- De-terminalizes `unprocessable_ocr` (removes it from `TERMINAL`, adds outgoing
  edges); recovery replaces the stored PDF bytes with the OCR'd text-layer PDF.
  Every OCR attempt is an audit record (success transitions; a non-recovering
  attempt is an access-style record). Does not touch `CLAUDE.md`,
  `.claude/agents/`, CI.
