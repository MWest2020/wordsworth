## MODIFIED Requirements

### Requirement: Local OCR engine

OCR SHALL be accessed through an `OcrEngine` protocol backed by a local engine
(no cloud OCR). The engine SHALL produce a **text-layer PDF** — the scanned PDF
with a searchable text layer added (e.g. ocrmypdf) — returned as PDF bytes, NOT
raw text. This lets a recovered document flow through the existing `profile_pdf`
and `positioned_text` (pypdfium2) path unchanged. Engine failure SHALL raise
(loud), never silently skip a document.

#### Scenario: Injected local engine is used

- **WHEN** OCR recovery runs with an `OcrEngine` injected
- **THEN** a text-layer PDF is produced by that local engine and no cloud call is
  made

#### Scenario: The OCR output is a searchable PDF

- **WHEN** a scanned document is OCR'd
- **THEN** the returned bytes are a PDF whose text layer is extractable by the
  normal pdfium extraction path
