## MODIFIED Requirements

### Requirement: The redacted PDF has nothing under the box

The redacted PDF SHALL be produced by rasterising every page, painting the
rectangles into the raster, and rebuilding the document with reportlab. The
painting SHALL happen before the raster is encoded. It SHALL carry vector labels
(`[PERSOON n]`, from `legible.to_legible`) on the rectangles and an invisible
text layer in which the labels replace the redacted spans. Nothing SHALL be
copied from the source PDF: no metadata, no annotations, no outlines. The page
rasters SHALL be stored compressed, so that the size of the PDF is bounded per
page and not by the raw pixel count.

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

#### Scenario: A page costs a bounded number of bytes

- **WHEN** a page with text and a redaction box is rendered
- **THEN** the PDF is smaller, per page, than the budget set in the test, and
  far smaller than the uncompressed raster of that page

#### Scenario: Compression does not weaken the redaction

- **WHEN** the compressed PDF is rendered again and compared with the source
  page
- **THEN** the pixels inside every rectangle are still the box colour and the
  redacted value is not legible in it
