# Tasks — add-ocr

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. OCR engine
- [ ] 1.1 `ocr.py`: `OcrEngine` protocol `ocr(pdf_bytes) -> bytes` returning a
      TEXT-LAYER PDF (ocrmypdf, nld) + test double returning a fixed text-layer
      PDF; engine failure raises
- [ ] 1.2 Tests: injected engine used; failure raises (no silent skip)

## 2. State machine
- [ ] 2.1 Remove `UNPROCESSABLE_OCR` from `TERMINAL`; add
      `UNPROCESSABLE_OCR → {EXTRACTABLE, FAILED}` to `ALLOWED`
- [ ] 2.2 Tests: the new edges are allowed; other transitions unchanged

## 3. Recovery flow
- [ ] 3.1 Recovery step: OCR an `unprocessable_ocr` doc, re-classify the text-layer
      PDF with the existing `profile_pdf`; at/above threshold replace the stored
      bytes with the OCR'd PDF and transition to `extractable`; else stay
- [ ] 3.2 Audit every attempt: on "stay", append an access-style OCR record
      (from=to=unprocessable_ocr, step="ocr", metric payload) — not a no-op
- [ ] 3.3 Tests: usable OCR -> extractable + audit record + extract reads the OCR
      text layer; too little -> unchanged but an OCR attempt record is written
