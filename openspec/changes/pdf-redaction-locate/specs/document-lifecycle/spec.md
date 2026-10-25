## MODIFIED Requirements

### Requirement: Born-digital detection

The transition out of `registered` SHALL parse the document with the single PDF
extraction `positioned_text` (pypdfium2, `text_source` `pdfium-v1`), count
extractable characters per page, and classify the document as `extractable`
when characters-per-page is at or above the configured threshold, or
`unprocessable_ocr` when below it. The raw `chars`, `pages`, and `bytes` values
SHALL be recorded in the transition's audit payload.

#### Scenario: Born-digital document is extractable

- **WHEN** a PDF yields characters-per-page at or above the threshold
- **THEN** its state becomes `extractable` and the audit payload holds the raw
  chars, pages, and bytes

#### Scenario: Scanned document is unprocessable

- **WHEN** a PDF yields characters-per-page below the threshold
- **THEN** its state becomes `unprocessable_ocr` (terminal for the PoC) and the
  raw metric is recorded

#### Scenario: Parser crash fails loudly

- **WHEN** the PDF parser raises while parsing a document
- **THEN** the document transitions to `failed` with the error reason, and is
  NOT classified as `unprocessable_ocr`

### Requirement: Text extraction

The `extract` transition SHALL pull the document's text with `positioned_text`
(pypdfium2, `text_source` `pdfium-v1`) and hold it in memory for anonymization.
Detection, `DocumentText`, the index text and the box map SHALL all use this
same text. A space SHALL be inserted where two characters on one line are
further apart than a fixed fraction of the character height and pdfium emitted
none; an inserted space has no char box. Extraction SHALL NOT persist clear
text. If extraction raises, the document SHALL transition to `failed` (loud
failure, no silent skip).

#### Scenario: Extractable document yields text

- **WHEN** the extract step runs on an `extractable` document
- **THEN** the document moves to `extracted`, an audit record is written, and no
  clear text is persisted

#### Scenario: Words pdfium joins get a space

- **WHEN** two characters on one line are further apart than the fixed fraction
  of the character height and pdfium emitted no space between them
- **THEN** the extracted text has a space there and that space has no char box

## ADDED Requirements

### Requirement: The anonymize record names its text source

The audit record of `anonymize` and `reanonymize` SHALL carry `text_source`
(`pdfium-v1` for a PDF extracted by `positioned_text`). The backfill SHALL pick
up every document whose record lacks `pdfium-v1` and SHALL report orphaned token
counts, never values.

#### Scenario: The record carries the source

- **WHEN** a PDF document is anonymised or reanonymised
- **THEN** its audit record has `text_source` `pdfium-v1`

#### Scenario: The backfill picks up documents without pdfium-v1

- **WHEN** the backfill runs over one document recorded without `text_source` and
  one recorded with `pdfium-v1`
- **THEN** only the first is re-derived and the run reports its orphaned token
  counts without any value
