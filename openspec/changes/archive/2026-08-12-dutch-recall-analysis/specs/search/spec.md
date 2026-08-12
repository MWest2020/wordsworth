## MODIFIED Requirements

### Requirement: Document-level BM25 indexing

The `OpenSearchIndex` driver SHALL index one document per source document (id =
source document id), scored by BM25. Indexing SHALL be an idempotent upsert. The
text SHALL be analysed for Dutch with a precision field (lowercase, asciifolding,
Dutch stopwords, Dutch stemmer) AND an n-gram recall sub-field so that Dutch
compounds/substrings are retrievable without a decompounding dictionary. Lexical
queries SHALL score over both fields, with the stemmed field boosted above the
recall sub-field.

#### Scenario: Indexed document is retrievable by keyword

- **WHEN** a document's anonymized text is indexed and a query matching its terms
  is searched
- **THEN** the document appears in the ranked hits with a positive score

#### Scenario: A compound is found by one of its parts

- **WHEN** a document contains a Dutch compound (e.g. "kostenonderbouwing") and a
  query uses one part of it (e.g. "kosten")
- **THEN** the document is retrieved via the recall sub-field

#### Scenario: Re-indexing the same id does not duplicate

- **WHEN** the same document id is indexed twice
- **THEN** the index holds a single document for that id
