# Tasks — add-anonymization-adapter

Done = green: every task ships with its tests in the same builder run.

## 1. Deterministic detectors
- [x] 1.1 `detectors.py`: BSN via elfproef, IBAN via mod-97, email regex —
      each finds valid matches, validating before it counts
- [x] 1.2 Tests: valid BSN/IBAN replaced, invalid left untouched, email replaced

## 2. Anonymizer seam
- [x] 2.1 `anonymizer.py`: `Anonymizer` protocol + `AnonymizationResult`
      (text + per-type counts)
- [x] 2.2 `DeterministicAnonymizer` implementing the protocol via the detectors
- [x] 2.3 Tests: replaces BSN/IBAN/email with typed placeholders, returns counts,
      leaves other text; a custom injected driver is honoured

## 3. Real text extraction
- [x] 3.1 `extraction.py`: `extract_text(bytes) -> str` (pypdf, all pages)
- [x] 3.2 Tests: born-digital PDF yields its text

## 4. Persistence
- [x] 4.1 `document_texts` table (document_id, anonymized_text) — anonymized text
      only; derived working data, not append-only, holds no PII

## 5. Pipeline wiring
- [x] 5.1 `process()` gains injected `anonymizer` (defaults to deterministic)
- [x] 5.2 `extract` real: pull text in memory (extract raise -> failed)
- [x] 5.3 `anonymize` real: run anonymizer, persist anonymized text, audit counts
- [x] 5.4 `index` stays a stub
- [x] 5.5 Tests: end-to-end with PII -> persisted text is PII-free, counts in
      audit; custom injected anonymizer is used; chain still verifies

## 6. Regression
- [x] 6.1 Existing add-pipeline-skeleton tests still pass (clean text -> indexed)
