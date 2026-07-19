## MODIFIED Requirements

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
