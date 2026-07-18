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
- [ ] 2.1 Recovery stores the OCR'd text-layer PDF via the `ObjectStore` under its
      own content-addressed key (`documents/` + sha256 of the OCR'd bytes) and
      updates `documents.object_key`; the original scan object is kept. Then
      re-classify with `profile_pdf(ocr_bytes, …)`; at/above threshold →
      transition to `extractable` (audit payload carries old+new object keys),
      else stay
- [ ] 2.2 Audit every attempt: on "stay", append an access-style record
      (from=to=unprocessable_ocr, step="ocr", metric payload) — not a no-op
- [ ] 2.3 Tests: usable OCR → extractable AND the extract→index path reads the OCR
      text layer (non-empty indexed content); sub-threshold → stays + an OCR
      attempt record is written

## 3. Reconcile with store-based process (#18)
- [ ] 3.1 Recovery + OCR tests use the store-based `process(session, id, store, …)`
      (bytes via the injected `ObjectStore`), not bytes-as-3rd-arg
- [ ] 3.2 Same defect class elsewhere: `tests/test_metrics.py`,
      `tests/test_structured_log.py`, `tests/test_throughput_report.py` also pass
      bytes as the 3rd `process` arg (`AttributeError: 'bytes' object has no
      attribute 'get'` when the DB-gated suite actually runs) — reconcile those
      call sites with the store-based `process` too (mechanical call-site fix; no
      behavior change to metrics/logging/reporting themselves)
- [ ] 3.3 Recovery-flow tests exercise the full extract→index path and are not
      silently skipped when they would catch content loss
