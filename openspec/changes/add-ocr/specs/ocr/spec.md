## ADDED Requirements

### Requirement: Local OCR engine produces a searchable PDF

OCR SHALL be accessed through an `OcrEngine` protocol backed by a local engine
(no cloud OCR). The engine SHALL produce a **text-layer PDF** (e.g. ocrmypdf) —
the same PDF with a searchable text layer added — NOT raw text, so the recovered
document flows through the existing `profile_pdf` and `extract_text` (pypdf) path
unchanged. Engine failure SHALL raise (loud), never silently skip a document.

#### Scenario: Injected local engine is used

- **WHEN** OCR recovery runs with an `OcrEngine` injected
- **THEN** a text-layer PDF is produced by that local engine and no cloud call is
  made

### Requirement: unprocessable_ocr is recoverable, not terminal

`unprocessable_ocr` SHALL cease to be a terminal state: it SHALL gain outgoing
edges to `extractable` and `failed`. An `unprocessable_ocr` document SHALL be run
through OCR, and its text-layer PDF re-classified by the same
characters-per-page threshold via `profile_pdf`: at/above threshold it becomes
`extractable` (the recovered PDF bytes replace the stored bytes so extraction
reads the OCR text layer); below, it remains `unprocessable_ocr`. Every OCR
attempt SHALL be recorded in the audit trail — including one that does not
recover — so the attempt is auditable and not silently re-run forever.

#### Scenario: OCR yields usable text

- **WHEN** OCR of a scanned document produces a text-layer PDF at/above the
  threshold
- **THEN** the recovered PDF bytes replace the stored bytes, the document becomes
  `extractable`, and an audit record is written

#### Scenario: OCR yields too little text but the attempt is recorded

- **WHEN** OCR produces text below the threshold
- **THEN** the document remains `unprocessable_ocr` AND an audit record of the OCR
  attempt (with the metric) is written, so it is not a silent no-op
