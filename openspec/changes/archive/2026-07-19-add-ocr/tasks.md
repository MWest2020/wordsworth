# Tasks — add-ocr

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.

## 1. OCR engine
- [x] 1.1 `ocr.py`: `OcrEngine` protocol + local engine (tesseract/ocrmypdf, nld)
      + test double; engine failure raises
- [x] 1.2 Tests: injected engine used; failure raises (no silent skip)

## 2. Recovery flow
- [x] 2.1 Recovery step: OCR an `unprocessable_ocr` doc, re-apply the born-digital
      threshold, transition to `extractable` or stay `unprocessable_ocr`
- [x] 2.2 Tests: usable OCR -> extractable + audit record; too little -> unchanged
