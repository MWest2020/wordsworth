## ADDED Requirements

### Requirement: A generated corpus carries its own ground truth

The evaluation corpus generator SHALL write each document together with the
answer for that document: the PII spans it contains (offset, type, value), the
topic it belongs to, and which declared combinations it carries in full.

The ground truth SHALL be produced by the same step that produces the text, from
the same values. An annotation pass over already-written text is a second source
of truth and will disagree with the first.

#### Scenario: Every declared span is exactly the text at that offset

- **WHEN** the generator writes a document and its gold entities
- **THEN** for every entity, `text[start:end]` equals the value that was
  inserted, and the generator fails rather than emitting a corpus if it does not

#### Scenario: Identifiers are valid but belong to nobody

- **WHEN** the generator emits a BSN or IBAN
- **THEN** it passes the elfproef respectively mod-97 — an invalid identifier
  tests nothing — and is drawn from a generated range, never from a real person

#### Scenario: The corpus states what it cannot tell you

- **WHEN** an evaluation report is produced over a generated corpus
- **THEN** it names the corpus as synthetic and states that the score is a lower
  bound for the machinery rather than a prediction for production text

### Requirement: One generation serves both evaluations

The generator SHALL emit, from a single run over a single set of documents, the
gold file the PII evaluation reads and the queries and relevance judgements the
ranking evaluation reads.

Two corpora produce two numbers that cannot be held next to each other. The
point of measuring both is to see them together.

#### Scenario: Relevance is derived, not guessed

- **WHEN** the generator assigns a relevance grade for a query to a document
- **THEN** the grade follows from the topic the document was generated for, and
  documents of an unrelated topic are graded irrelevant rather than omitted
