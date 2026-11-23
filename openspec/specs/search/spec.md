# search Specification

## Purpose

Keyword retrieval: an index protocol, BM25 at document level, ranked hits.

The protocol comes first because the index is the component most likely to be
swapped — and because an analysis pipeline that can only run against one engine
cannot be evaluated against alternatives.

The rule that governs everything upstream of this: **no PII reaches the index.**
Search is the part of the system with the widest audience, so it operates on
de-identified text only. That is why anonymisation sits before indexing in the
pipeline and not after.

## Requirements

### Requirement: Search index protocol

Indexing and search SHALL be accessed through a `SearchIndex` protocol returning
typed `Hit` results, so the backend is swappable and the pipeline never depends
on a concrete search engine. Indexing SHALL accept an optional per-document
vector, and the protocol SHALL provide a `hybrid_search` method that returns an
RRF-fused recall set carrying each candidate's vector.

#### Scenario: A custom index is used when injected

- **WHEN** a caller injects an object satisfying the `SearchIndex` protocol
- **THEN** the pipeline uses it for the index step instead of the default

#### Scenario: Hybrid recall returns candidates with vectors

- **WHEN** `hybrid_search` is called with a query and a query vector
- **THEN** it returns RRF-fused candidates, each carrying its stored vector for
  the final cosine ranking

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

### Requirement: Keyword search returns ranked hits

Search SHALL accept a free-text query and return document hits ranked by BM25
score, each carrying the document id and score.

#### Scenario: More relevant document ranks higher

- **WHEN** two documents are indexed and a query matches one far more than the
  other
- **THEN** the stronger match ranks above the weaker one

#### Scenario: Search is exposed over the API

- **WHEN** `GET /search?q=<terms>` is called
- **THEN** it returns the ranked hits for the query

### Requirement: A superseded document leaves the index

The `SearchIndex` protocol SHALL provide `delete(doc_id)`, and superseding a
document SHALL remove its entry, so a search never returns the same stored
object twice.

#### Scenario: Copies no longer show up in search

- **WHEN** a document with an index entry is superseded
- **THEN** its entry is gone and a search that matched it returns only the
  surviving document

### Requirement: A search result shows why it matched

Each of the first ten search results in the console SHALL show the passage of
the document closest to the question, cut from the stored pseudonymised text,
with the query words that occur in it marked, and a short reason stating
whether the passage matches on words, on meaning, or both. The stored text
SHALL reach the page as text: nothing in it is interpreted as markup. Showing the passage SHALL NOT change the
order of the results and SHALL NOT store anything in the index.

When the closest passage cannot be determined for a hit, the result SHALL show
the fragment shown before this change. When the cause is that the index cannot
be read for the passages, the page SHALL say that the passages are unavailable.

#### Scenario: The closest passage is shown

- **WHEN** a question is closest to the second passage of a document in the results
- **THEN** the result shows that passage, as it stands in the stored pseudonymised text, and the reason

#### Scenario: A semantic match is explained

- **WHEN** the closest passage shares no word with the question
- **THEN** the reason says it matched on meaning and no word is marked

#### Scenario: Markup in a document stays text

- **WHEN** the closest passage of a hit contains `<script>` in its stored text
- **THEN** the page shows those characters as text and runs nothing

#### Scenario: The order of results is unchanged

- **WHEN** the same question is asked with and without passages available
- **THEN** the results are the same documents in the same order

#### Scenario: The stored vectors do not fit the text

- **WHEN** the number of passage vectors stored for a hit differs from the number of passages its stored text splits into
- **THEN** the result shows the fragment as before, without a reason

#### Scenario: The index cannot be read for the passages

- **WHEN** the results are in but reading their passage vectors fails because the index is unreachable, or the question cannot be embedded for the comparison
- **THEN** every result shows the fragment as before and the page says the passages are unavailable
