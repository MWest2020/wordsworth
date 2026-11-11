# ocr Specification

## Purpose

Getting text out of documents that do not have any: scanned pages, through a
local engine.

Government archives are full of scans, so without OCR a large part of the corpus
is invisible to search — not wrong, just silently absent, which is worse.

**Local** is the requirement that matters. These are documents whose contents may
not leave the country, let alone the organisation; an OCR service in someone
else's cloud would undo the privacy posture of every other capability here before
anonymisation ever ran.

## Requirements

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
Before anything is written, recovery SHALL check whether another live document
owns the new key; if so it SHALL write nothing and retire the scan's document
as a copy of that owner. Otherwise the OCR'd PDF SHALL be stored sealed,
through the originals store, under a key row of the recovered document.

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

#### Scenario: The OCR'd PDF is stored sealed

- **WHEN** a scanned document is recovered and no other live document owns the
  OCR'd bytes
- **THEN** the new object carries the sealed header, opens to the OCR'd bytes
  and has a key row of the recovered document

#### Scenario: Another document's object is never overwritten

- **WHEN** the OCR'd bytes are already the object of another live document
- **THEN** that object is unchanged, nothing is written, and the scan's
  document is superseded by the owner
