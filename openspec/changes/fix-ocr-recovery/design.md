# Design decisions — fix-ocr-recovery

## Text-layer PDF, not raw text (fixes #16)

ocrmypdf already produces a searchable PDF (`out.pdf`) with a text layer. The bug
is that the built engine discards it and returns only the sidecar `.txt`. The fix:
`OcrEngine.ocr(pdf_bytes) -> bytes` returns that text-layer PDF. Recovery stores it
through the `ObjectStore` under its **own content-addressed key** and updates
`documents.object_key` to point at it, so the normal path — `profile_pdf` then
`extract_text` (pypdf) — fetches the OCR'd PDF with no OCR-specific extract branch.
This is what makes a recovered doc flow "like any other document".

Not under the existing key: object keys are content-addressed (`documents/` +
sha256 of the bytes, `pipeline.py`). Overwriting the scanned original's key with
different bytes would break `key == sha256(bytes)` and destroy the source scan —
unauditable and unrecoverable (no re-OCR with a better engine later). The audit
record of a recovering attempt carries old and new object keys, so the switch is
traceable.

Re-classification therefore runs `profile_pdf(ocr_pdf_bytes, threshold)` on the
text-layer PDF (a real PDF), not on raw text — the built code could only count
chars on a str, which is the tell of the raw-text mistake.

## Audit every attempt (fixes #17)

A non-recovering attempt must leave a trace. A same-state `transition()` is an
idempotent no-op that writes nothing, so record the attempt as an access-style
event: `audit.append(from_state=to_state=unprocessable_ocr, step="ocr",
payload=metric)` — the pattern `deanonymize` already uses. This keeps the audit
table the orchestration state and prevents blind infinite re-OCR.

## Reconcile with the store-based process (fixes #18)

The OCR branch was built against the older `process(session, id, pdf_bytes)`;
#13 integrated it against `process(session, id, store, ...)` without reconciling.
Recovery must obtain/replace bytes via the injected `ObjectStore`, and the
recovery-flow tests must call `process` with a store (like `test_pipeline`/
`test_e2e`) and assert the full extract→index path so content-loss is caught —
not stop at `extractable` behind a DB-gated skip.

## Not in scope

OCR quality/tuning, layout/table reconstruction — unchanged from the original
add-ocr scope.
