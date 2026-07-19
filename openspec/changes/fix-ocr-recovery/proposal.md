## Why

The built OCR recovery (merged in #13) loses content. Fixes issues #16, #17, #18.

- **#16 (data loss, high):** `OcrEngine.ocr` returns raw text; ocrmypdf's text-layer
  PDF is discarded and never persisted. After recovery sets a doc `extractable`,
  `process` re-extracts the **original scanned bytes** via pypdf → empty. The
  document is anonymized and indexed with no content.
- **#17 (invariant):** a sub-threshold OCR attempt writes no audit record — it
  "stays" `unprocessable_ocr` as a silent no-op, violating "every step transition
  is an audit record".
- **#18 (integration, high):** the recovery test passes PDF bytes where the
  store-based `process(session, document_id, store, ...)` expects an `ObjectStore`;
  the recovery tests are DB-gated and skipped, so this passed CI.

## What Changes

- `OcrEngine.ocr(pdf_bytes) -> bytes` returns a **text-layer PDF** (ocrmypdf's
  searchable PDF), not raw text.
- Recovery **stores the OCR'd text-layer PDF as a new content-addressed object**
  (keys are `documents/` + sha256 of the bytes — overwriting the old key would
  break `key == sha256(bytes)`) and updates the document's `object_key`; the
  original scan is kept. Re-classification uses the existing `profile_pdf`;
  at/above threshold → `extractable` (the normal `extract_text` path fetches by
  the updated key and reads the OCR text layer).
- **Every OCR attempt is audited**, including a non-recovering one (access-style
  `audit.append(from=to=unprocessable_ocr, step="ocr", payload=metric)`).
- Recovery and its tests are reconciled with the store-based `process`; the
  recovery-flow tests exercise the full extract→index path (not DB-gated away).

## Capabilities

### Modified Capabilities
- `ocr`: engine returns a text-layer PDF; recovery persists it and audits every
  attempt.

## Impact

- Corrects `src/wordsworth/ocr.py`, `recovery.py`, and the OCR tests. Reuses
  `profile_pdf`/`extract_text` and the object store (OCR'd PDF stored via the
  `ObjectStore` seam under its own content-addressed key; `documents.object_key`
  updated). Does not touch `CLAUDE.md`, `.claude/agents/`, or CI.
- Archive-order: archive only after `add-ocr` is archived — the baseline
  `openspec/specs/` does not carry this capability until then.
