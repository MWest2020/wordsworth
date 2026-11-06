## ADDED Requirements

### Requirement: A long synthetic PDF corpus with known answers

The project SHALL provide a generator that writes a corpus of long synthetic PDF
documents with page-level ground truth for personal data, in the format the PII
evaluation reads, and known answers for search, built only from values that cannot
belong to a real person. Pages without a text layer SHALL be kept out of the gold that
is scored.

#### Scenario: Gold is one record per page in the evaluation's format

- **WHEN** the generator writes a corpus
- **THEN** `gold.jsonl` holds one line per born-digital page with `id`, `doc`, `page`, `text` and `entities` (offsets in that page's text), and `load_gold` reads it

#### Scenario: Gold matches the pages

- **WHEN** the generator writes a corpus
- **THEN** every planted value of a born-digital page appears in that page's extracted text

#### Scenario: Scanned pages are kept out of the scored gold

- **WHEN** a page is rendered as an image
- **THEN** it has no text layer, its gold is in `gold_scanned.jsonl`, and it has no line in `gold.jsonl`

#### Scenario: The answer page is never scanned

- **WHEN** the generator chooses scanned pages
- **THEN** neither page 1 nor the page holding the document's planted answer is among them

#### Scenario: Detections equal gold

- **WHEN** the deterministic detectors run over a born-digital page's extracted text
- **THEN** they find exactly that page's gold spans for BSN, IBAN, e-mail and postcode, no more and no fewer

#### Scenario: Values cannot be anyone's

- **WHEN** the generator plants a BSN or an IBAN
- **THEN** the BSN lies in the published test range 999990000–999999999 and passes the elfproef, and the IBAN uses the non-existent bank code `ZZZZ` and passes mod-97

#### Scenario: A late answer

- **WHEN** the generator writes the queries
- **THEN** each document's query is answered only by a phrase on a page at or after page 20 (or its last page), recorded in `manifest.json`

#### Scenario: Reproducible

- **WHEN** the generator runs twice with the same seed, options and environment
- **THEN** it writes identical files, and the gold files are identical in any environment
