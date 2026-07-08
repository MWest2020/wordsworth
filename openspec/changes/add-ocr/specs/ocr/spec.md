## ADDED Requirements

### Requirement: Local OCR engine

OCR SHALL be accessed through an `OcrEngine` protocol backed by a local engine;
no cloud OCR SHALL be used. Engine failure SHALL raise (loud), never silently
skip a document.

#### Scenario: Injected local engine is used

- **WHEN** OCR recovery runs with an `OcrEngine` injected
- **THEN** text is produced by that local engine and no cloud call is made

### Requirement: OCR recovery of scanned documents

An `unprocessable_ocr` document SHALL be run through OCR and re-classified by the
same characters-per-page threshold: at/above threshold it becomes `extractable`;
below, it remains `unprocessable_ocr`. The transition SHALL be recorded in the
audit trail.

#### Scenario: OCR yields usable text

- **WHEN** OCR of a scanned document produces text at/above the threshold
- **THEN** the document becomes `extractable` and an audit record is written

#### Scenario: OCR yields too little text

- **WHEN** OCR produces text below the threshold
- **THEN** the document remains `unprocessable_ocr`
