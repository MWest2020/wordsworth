## ADDED Requirements

### Requirement: Ranker adapters

The system SHALL provide adapters that expose BM25 and hybrid search as the
harness's `search(query) -> ranked document ids` callable, each returning the
documents' external ids (`object_key`) so results align with the qrels namespace.
Adapters SHALL retrieve to a configurable **depth** (at least `max(k, max R)`),
distinct from the metric cutoff `k`, so R-Precision and MAP are not deflated by
truncation. The hybrid adapter SHALL raise `recall` to that depth as well, since
`hybrid_search` caps results at `recall`. A null `object_key` SHALL NOT be emitted
into the ranking.

#### Scenario: BM25 adapter returns ranked external ids

- **WHEN** the BM25 adapter is called with a query
- **THEN** it returns the ranked list of matching documents' external ids

#### Scenario: Hybrid adapter returns ranked external ids

- **WHEN** the hybrid adapter is called with a query
- **THEN** it returns the ranked external ids from hybrid retrieval

#### Scenario: Adapters retrieve beyond the metric cutoff

- **WHEN** an adapter is built with a depth greater than `k`
- **THEN** it returns more than `k` ranked ids (and the hybrid adapter's `recall`
  is at least that depth), so relevant documents beyond rank `k` are scored

### Requirement: Evaluation run over a real collection

The system SHALL run the evaluation harness over a loaded collection for one or
more configurations and produce a report of per-configuration aggregate metrics
(R-Precision, Recall@10, MAP, NDCG@10).

#### Scenario: Report contains a result per configuration

- **WHEN** an evaluation run is executed for the BM25 and hybrid configurations
- **THEN** the report contains the four aggregate metrics for each configuration

#### Scenario: Qrels ids match indexed documents by external id

- **WHEN** the corpus is indexed with `object_key` equal to the qrels' document
  ids and a run is executed
- **THEN** ranked ids and qrels ids share one namespace and the metrics are
  computed over matching documents

### Requirement: Runnable from a CLI

The evaluation run SHALL be invocable from a command line, given the qrels and
queries files and the chosen configurations.

#### Scenario: CLI runs an evaluation

- **WHEN** the CLI is invoked with qrels, queries, and configurations
- **THEN** it loads the collection, runs the configurations, and prints the report
