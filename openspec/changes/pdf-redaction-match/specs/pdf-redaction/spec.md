## MODIFIED Requirements

### Requirement: A box map locates values by word, never by offset

The system SHALL compute, inside `process` and `reanonymize`, a box map for a
PDF document: for each redaction the page, the rectangle and the token. The box
map SHALL hold no value and SHALL never be persisted with values. Each detected
value SHALL be located whole-word in the pypdfium2 positioned text, never by
character offsets taken from the pypdf text. A value broken over two lines SHALL
give one rectangle per line. The positioned text of an OCR'd scan SHALL come from
its existing ocrmypdf `object_key`. A line break in the positioned text SHALL act
as a word separator, so the last word of a line is never joined to the first word
of the next. The words of a value SHALL match with optional whitespace between
them. Matching SHALL follow the normalisation rule of the value's type:
case-insensitive for types whose rule is casefold (PERSON, ORGANIZATION,
LOCATION, EMAIL) and whitespace-insensitive for POSTCODE.

#### Scenario: A two-line name gives two rectangles

- **WHEN** a detected name is split over two lines of a page
- **THEN** the box map has two rectangles for it, on that page, with the same
  token

#### Scenario: The box map holds no value

- **WHEN** a box map is persisted
- **THEN** it contains page, rectangle and token only, and none of the detected
  values

#### Scenario: A value at the end of a line is located

- **WHEN** a value is the last word of a line and another word starts the next
  line
- **THEN** the value is located and the box covers only the value

#### Scenario: A value that spans a line break is located

- **WHEN** a detected value contains a line break between two of its words
- **THEN** it is located, with one rectangle per line

#### Scenario: A stored spelling that differs in case is located

- **WHEN** the stored value of a PERSON token differs in case from the page
- **THEN** the page text is located and boxed

#### Scenario: A postcode spaced differently is located

- **WHEN** the stored postcode has no space and the page has one
- **THEN** the page text is located and boxed

### Requirement: Reprocess reports every value that could not be located

`POST /reprocess` SHALL list every `value-not-located` outcome in `problems`,
naming the document, the PII type and the counts, never the value. The counts
SHALL read located first, then the number of occurrences in the text (`0 of 1
located` when 1 occurs and none is located).

#### Scenario: Reprocess reports a value-not-located

- **WHEN** a reprocess run hits `value-not-located` for a document
- **THEN** the response `problems` is non-empty and names that document

#### Scenario: The counts are in the right order

- **WHEN** a token occurs once in the text and none is located
- **THEN** the problem reads `0 of 1 located`
