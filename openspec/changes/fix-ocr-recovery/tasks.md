# Tasks — fix-ocr-recovery

Done = green: every task ships with its tests. NOTE: unchecked — for a Habitat builder.
Fixes #16, #17, #18.

## 1. Engine returns a text-layer PDF (#16)
- [ ] 1.1 `OcrEngine.ocr(pdf_bytes) -> bytes` returns ocrmypdf's text-layer PDF
      (stop discarding `out.pdf`; do not return raw text); test double returns a
      fixed text-layer PDF
- [ ] 1.2 Tests: the returned bytes are a PDF whose text layer is extractable by
      `extract_text` (pypdf)

## 2. Recovery persists + re-classifies + audits (#16, #17)
- [ ] 2.1 Recovery replaces the stored object bytes with the OCR'd text-layer PDF
      via the `ObjectStore`, then re-classifies with `profile_pdf(ocr_bytes, …)`;
      at/above threshold → transition to `extractable`, else stay
- [ ] 2.2 Audit every attempt: on "stay", append an access-style record
      (from=to=unprocessable_ocr, step="ocr", metric payload) — not a no-op
- [ ] 2.3 Tests: usable OCR → extractable AND the extract→index path reads the OCR
      text layer (non-empty indexed content); sub-threshold → stays + an OCR
      attempt record is written

## 3. Reconcile with store-based process (#18)
- [ ] 3.1 Recovery + OCR tests use the store-based `process(session, id, store, …)`
      (bytes via the injected `ObjectStore`), not bytes-as-3rd-arg
- [ ] 3.2 Recovery-flow tests exercise the full extract→index path and are not
      silently skipped when they would catch content loss
