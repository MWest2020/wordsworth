# evaluation Specification

## Purpose

Measuring whether retrieval is any good: IR metrics, a runner that does not care
which ranker, and standard test collections.

Without this, "we improved search" is an opinion. The runner is deliberately
**ranker- and collection-agnostic**, because an evaluation harness married to one
implementation can only ever confirm it.

**PII detection metrics** live here too, and that is the important part: precision
and recall on detection are a safety measure, not a quality metric. Knowing how
much is missed is the difference between a privacy claim and a privacy hope.

## Requirements

### Requirement: IR metric functions

The system SHALL provide pure functions computing R-Precision, Recall@k (k=10 by
default), Average Precision, and NDCG@k over a ranked list of document ids and
graded relevance judgments. Binary metrics SHALL treat any relevance grade > 0 as
relevant; NDCG SHALL use the grade as gain. Each metric SHALL return 0.0 when
there are no relevant documents (or, for NDCG, no ideal gain).

#### Scenario: R-Precision on a known ranking

- **WHEN** 2 of the top-2 ranked documents are relevant and there are 2 relevant
  documents in total
- **THEN** R-Precision is 1.0

#### Scenario: Recall@10 counts relevant in the top 10

- **WHEN** 3 of 5 relevant documents appear in the top 10 ranked
- **THEN** Recall@10 is 0.6

#### Scenario: Average Precision rewards early relevant hits

- **WHEN** the same relevant documents are ranked earlier rather than later
- **THEN** the Average Precision is higher

#### Scenario: NDCG uses graded gains and ideal ordering

- **WHEN** documents are ranked in the ideal (grade-descending) order
- **THEN** NDCG@k is 1.0

#### Scenario: No relevant documents yields zero

- **WHEN** a query has no relevant documents in the qrels
- **THEN** every metric returns 0.0

### Requirement: Ranker- and collection-agnostic runner

The evaluation runner SHALL accept a ranker callable (`query text -> ranked
document ids`), a set of queries, and qrels, and SHALL produce per-query metrics
and their means. It SHALL depend on nothing but the callable — no database,
search engine, or embedding service. Per-query results SHALL report Average
Precision under the key `ap`; the aggregate mean of AP SHALL be reported as `map`
(MAP is a mean over queries and exists only at the aggregate level).

#### Scenario: Evaluate an arbitrary ranker

- **WHEN** the runner is given a ranker callable, queries, and qrels
- **THEN** it returns per-query metrics (with `ap` per query) and aggregate means
  over the queries (with `map` as the mean AP)

#### Scenario: Same harness evaluates different rankers

- **WHEN** two different rankers are evaluated on the same collection
- **THEN** each is scored by the same metrics with no harness change

### Requirement: Standard test-collection loaders

The system SHALL load a test collection from disk: qrels in TREC format
(`query_id 0 doc_id relevance`) and queries as TSV (`query_id<TAB>text`), so a
real collection (e.g. the thesis's queries and judgments) can be evaluated
without code changes.

#### Scenario: Load TREC qrels and TSV queries

- **WHEN** qrels and queries files in the specified formats are loaded
- **THEN** they parse into the in-memory qrels and queries structures the runner
  consumes

### Requirement: PII detection metrics

The evaluation library SHALL compute, for a gold corpus of annotated spans,
precision, recall and F1 per entity type and overall, at span level (exact
match) and token level (overlap), and SHALL report the number of gold entities
with no overlapping detection (`leaks`). When detections carry a layer, the
metrics SHALL also be reported per layer.

#### Scenario: Exact and partial matches are distinguished

- **WHEN** gold has `Janine van Dijk` and the detector finds `van Dijk`
- **THEN** span-level recall for PERSON is 0, token-level recall is 2/3, and
  `leaks` is 0

#### Scenario: A missed entity is a leak

- **WHEN** a gold BSN has no overlapping detection
- **THEN** `leaks` increases by one and BSN recall decreases accordingly

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

### Requirement: A pilot report is made from a template with Mark's gate slots empty

The published-dossier pilot SHALL have a report template with sections for the
check, the corpus, the ranking gate, the PII gate and the findings. The check
section SHALL carry `checked_by`, `checked_at`, `robots_txt`, `anubis` and
`decision` from the pilot's `check.json`. The corpus section SHALL carry the
number of documents, the number of pages, the number of pages without a text
layer and the number of scans, and SHALL state that with no scans the OCR path
is barely tested. The ranking-gate and PII-gate sections SHALL be empty slots
that only Mark fills. A report made from the template SHALL leave a slot empty
until Mark fills it, and SHALL report a gate with an empty slot as not yet run,
not as passed.

#### Scenario: The template ships with empty gate slots

- **WHEN** the template is read
- **THEN** the ranking-gate and PII-gate sections contain no question, no
  timestamp and no identifier

#### Scenario: A gate whose slot is empty

- **WHEN** a report is written and Mark has not yet filled the ranking-gate or
  PII-gate slot
- **THEN** that gate is reported as not yet run, not as passed or failed

### Requirement: The ranking-gate slot proves the questions came first

The ranking-gate slot SHALL hold 5 questions each with the document Mark
expects, the time the questions were committed, the time of the first search
and the outcome. The gate SHALL pass when the expected document is in the top 8
for at least 4 of 5 questions, and SHALL be stated as gating this pilot run
only.

#### Scenario: Questions and timestamps are recorded

- **WHEN** Mark fills the ranking-gate slot
- **THEN** it holds 5 questions with expected documents, the commit time of the
  questions and the time of the first search

#### Scenario: Four of five in the top 8

- **WHEN** the expected document is in the top 8 for 4 of the 5 questions
- **THEN** the ranking gate passes for this pilot run

### Requirement: The PII-gate slot records Mark's read, not a recall figure

The PII-gate slot SHALL hold Mark's read of the anonymized text of the pilot
documents and any leftover direct identifier of a private person (name,
address, e-mail, phone, BSN, IBAN). The template and a report made from it
SHALL NOT use the word "recall" for PII, because published material is already
redacted by the municipality and there is no unredacted original to measure
misses against. The report SHALL state that anonymization of unpublished
documents remains unproven by this pilot.

#### Scenario: The word is absent

- **WHEN** the template is searched for the word "recall", case-insensitively
- **THEN** there is no match

#### Scenario: A leftover identifier

- **WHEN** Mark records a leftover direct identifier of a private person in a
  pilot document
- **THEN** the PII gate is reported as failed for that document unless it is
  excluded with the reason written down

### Requirement: The pilot report states the findings so far

The report SHALL state, as findings and not as fixes, that the 567-document
dossier `gooise-meren-woo-2022` has unknown provenance, and that provenance is
not recorded when a document is delivered again (a duplicate keeps its first
provenance and fails the manifest run).

#### Scenario: Findings are present

- **WHEN** a report is made from the template
- **THEN** it names both findings
