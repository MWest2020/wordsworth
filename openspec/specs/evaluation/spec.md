# evaluation Specification

## Purpose
TBD - created by archiving change add-evaluation-harness. Update Purpose after archive.
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

