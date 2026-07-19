## MODIFIED Requirements

### Requirement: Local OCR engine

OCR SHALL be accessed through an `OcrEngine` protocol backed by a local engine
(no cloud OCR). The engine SHALL produce a **text-layer PDF** — the scanned PDF
with a searchable text layer added (e.g. ocrmypdf) — returned as PDF bytes, NOT
raw text. This lets a recovered document flow through the existing `profile_pdf`
and `extract_text` (pypdf) path unchanged. Engine failure SHALL raise (loud),
never silently skip a document.

#### Scenario: Injected local engine is used

- **WHEN** OCR recovery runs with an `OcrEngine` injected
- **THEN** a text-layer PDF is produced by that local engine and no cloud call is
  made

#### Scenario: The OCR output is a searchable PDF

- **WHEN** a scanned document is OCR'd
- **THEN** the returned bytes are a PDF whose text layer is extractable by the
  normal pypdf extraction path

### Requirement: OCR recovery of scanned documents

An `unprocessable_ocr` document SHALL be run through OCR; the resulting text-layer
PDF SHALL be **stored as a new content-addressed object** (object keys are
`documents/` + sha256 of the bytes, so `key == sha256(bytes)` must keep holding)
and the document's `object_key` SHALL be updated to that new key — the original
scanned object SHALL NOT be overwritten or deleted. The document SHALL then be
re-classified by the same characters-per-page threshold via `profile_pdf` on that
PDF: at/above threshold it becomes `extractable` (the normal extract step fetches
by the updated key and reads the OCR text layer); below, it remains
`unprocessable_ocr`. Every OCR attempt SHALL be recorded in the audit trail —
including one that does not recover — so no attempt is a silent no-op; a
recovering attempt's audit record SHALL carry the old and new object keys.

#### Scenario: OCR yields usable text and is actually extractable

- **WHEN** OCR of a scanned document produces a text-layer PDF at/above the
  threshold
- **THEN** that PDF is stored under its own content-addressed key, the document's
  `object_key` points at it (the original scan object still exists), the document
  becomes `extractable`, an audit record with old and new object keys is written,
  and the subsequent extract step reads non-empty OCR text (not the empty
  original scan)

#### Scenario: Sub-threshold OCR attempt is recorded

- **WHEN** OCR produces text below the threshold
- **THEN** the document remains `unprocessable_ocr` AND an audit record of the OCR
  attempt (with the metric) is written — not a silent no-op
