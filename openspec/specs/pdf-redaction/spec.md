# pdf-redaction Specification

## Purpose
Created by the change `pdf-redaction`. Mark, via the odin coding session: *"what we want is the anonymising in the

## Requirements

### Requirement: A box map locates values by word, never by offset

The system SHALL compute, inside `process` and `reanonymize`, a box map for a
PDF document: for each redaction the page, the rectangle and the token. The box
map SHALL hold no value and SHALL never be persisted with values. Each detected
value SHALL be located whole-word in the pypdfium2 positioned text, never by
character offsets taken from the pypdf text. A value broken over two lines SHALL
give one rectangle per line. The positioned text of an OCR'd scan SHALL come from
its existing ocrmypdf `object_key`.

#### Scenario: A two-line name gives two rectangles

- **WHEN** a detected name is split over two lines of a page
- **THEN** the box map has two rectangles for it, on that page, with the same
  token

#### Scenario: The box map holds no value

- **WHEN** a box map is persisted
- **THEN** it contains page, rectangle and token only, and none of the detected
  values

### Requirement: A value that cannot be located fails hard

For each token, when its count in the anonymised text exceeds the whole-word
matches of its value in the positioned text (`positioned_text`, pypdfium2), the
system SHALL write a `value-not-located` audit record and
`GET /documents/{id}/redacted.pdf` SHALL answer 409 with no PDF. There SHALL be
no fallback to a partly redacted PDF.

#### Scenario: A value cannot be found in the positioned text

- **WHEN** a value occurs twice in the pypdf text and once in the positioned text
- **THEN** a `value-not-located` audit record exists and the endpoint answers
  409 without a PDF

#### Scenario: A token occurs more often than its value is located

- **WHEN** a token occurs twice in the anonymised text and its value has one
  whole-word match in the positioned text
- **THEN** a `value-not-located` audit record exists and the endpoint answers 409
  without a PDF

### Requirement: The redacted PDF has nothing under the box

The redacted PDF SHALL be produced by rasterising every page at 300 dpi,
painting the rectangles, and rebuilding the document with reportlab. It SHALL
carry vector labels (`[PERSOON n]`, from `legible.to_legible`) on the
rectangles and an invisible text layer in which the labels replace the redacted
spans. Nothing SHALL be copied from the source PDF: no metadata, no annotations,
no outlines.

#### Scenario: Name and BSN are gone from the text layer

- **WHEN** the text of the redacted PDF is extracted with pypdf and with pdfium
- **THEN** neither the known name nor the known BSN occurs

#### Scenario: The box covers the right place

- **WHEN** the redacted page is compared with the source page
- **THEN** every source character box of a redacted value lies inside a
  rectangle, the pixels there are the box colour, and the label is placed on the
  rectangle

#### Scenario: The raster does not show the name

- **WHEN** tesseract is run on the rendered page
- **THEN** it finds no redacted name

#### Scenario: Nothing is carried over

- **WHEN** the output PDF is inspected
- **THEN** it has none of the source metadata, annotations or outlines

### Requirement: The redacted PDF is served from a cache that knows when it is stale

`GET /documents/{document_id}/redacted.pdf` SHALL serve the redacted PDF, cached
under `redacted/<doc>/<boxmap_hash>`. It SHALL answer 409 `stale` when the
current `lists_hash` differs from the one the box map was made with. The
`reanonymize` operation SHALL regenerate the box map.

#### Scenario: A lists change, then stale, then reanonymize

- **WHEN** the detection lists change, the endpoint is called, `reanonymize` is
  run, and the endpoint is called again
- **THEN** the first call answers 409 `stale` and the last call serves a PDF made
  with the new lists

### Requirement: A grant reveals clear values in the PDF for granted types only

`POST /documents/{document_id}/reveal.pdf` with a grant SHALL draw clear values
for the types the grant allows and keep the label for every other type. The
result SHALL never be cached or stored. The reveal SHALL be audited as a
deanonymize with `view=pdf`, carrying the types and no clear value.

#### Scenario: Only the granted type is drawn

- **WHEN** a reveal PDF is requested with a grant for one type while the
  document also has another type
- **THEN** the PDF shows the clear value of the granted type, the other type
  keeps its label, no object is written under `redacted/`, and the audit record
  has `view=pdf` and no clear value

### Requirement: Reprocess reports every value that could not be located

`POST /reprocess` SHALL list every `value-not-located` outcome in `problems`,
naming the document, the PII type and the counts, never the value.

#### Scenario: Reprocess reports a value-not-located

- **WHEN** a reprocess run hits `value-not-located` for a document
- **THEN** the response `problems` is non-empty and names that document
