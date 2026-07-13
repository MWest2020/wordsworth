# Design decisions — add-ocr

## Seam and flow

`OcrEngine` protocol: `ocr(pdf_bytes) -> bytes` — returns a **text-layer PDF**
(the scanned PDF with a searchable text layer added), NOT raw text. Local
implementation: tesseract with the Dutch model via **ocrmypdf** (which produces
exactly such a PDF). A test double returns a fixed text-layer PDF. Raw-text
engines (bare pytesseract) are out: they would force a divergent extract path and
break `profile_pdf` reuse (see below).

Recovery flow, so a recovered doc is handled *like any other document*:

1. Run OCR on an `unprocessable_ocr` document → text-layer PDF bytes.
2. Re-classify with the **existing** `profile_pdf(ocr_bytes, threshold)` — this
   works only because the OCR output is a PDF; raw text could not be profiled by
   the pypdf-based profiler.
3. At/above threshold → **replace the stored bytes with the OCR'd PDF** and
   transition to `extractable`. The normal `extract_text` (pypdf) then reads the
   OCR text layer — no OCR-specific extract path.
4. Below threshold → stays `unprocessable_ocr`, but the attempt is still audited
   (next paragraph).

## State machine and auditing the attempt

`unprocessable_ocr` is currently in `TERMINAL` ("no outgoing edge"). This change
**removes it from `TERMINAL`** and adds `UNPROCESSABLE_OCR → {EXTRACTABLE, FAILED}`
to `ALLOWED`. A successful recovery is a normal `transition`.

A recovery that does NOT clear the threshold must still leave a trace: a
same-state `transition` is an idempotent no-op that writes no record. So record
the attempt as an **access-style audit event** — `audit.append(from_state=
unprocessable_ocr, to_state=unprocessable_ocr, step="ocr", payload=metric)`,
exactly the pattern `deanonymize` already uses for a non-transition event. This
keeps the audit table the orchestration state (an OCR attempt is visible) and
prevents blind infinite re-OCR.

OCR engine failure → loud error (transient/retryable), never a silent skip.

## Boundaries

- **Local only** — no cloud OCR. CPU is acceptable (nightly batch); throughput is
  measured and reported like the rest of the pipeline.
- OCR is opt-in and runs after the main pass, so it never delays the born-digital
  path (the "no OCR tuning before something is searchable" scoping rule).

## Not in scope

Layout reconstruction, table extraction, handwriting. Plain text recovery only.
