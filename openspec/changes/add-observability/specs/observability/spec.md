## ADDED Requirements

### Requirement: Metrics endpoint

The API SHALL expose `GET /metrics` in Prometheus text format, including document
counts per state, transition counts per step, and error (failed) counts, derived
from the audit table.

#### Scenario: Metrics reflect the audit state

- **WHEN** `GET /metrics` is called after documents have been processed
- **THEN** it returns Prometheus-format metrics whose per-state counts match the
  current document states

### Requirement: Structured logging

Pipeline transitions SHALL emit structured (JSON) log lines carrying at least the
document id and step. A line SHALL be emitted only when a transition actually
occurs — the idempotent no-op transition (which returns without appending a
record) SHALL NOT log. Per-transition duration is NOT logged at emit time (the
transition does not read the prior record's timestamp); stage timing is a
report-only computation (see Throughput reporting).

#### Scenario: A transition logs a structured line

- **WHEN** a document transitions between states
- **THEN** a JSON log line with the document id and step is emitted

#### Scenario: A no-op transition logs nothing

- **WHEN** a transition is requested whose target equals the current state
- **THEN** no record is appended and no log line is emitted

### Requirement: Throughput reporting

The run report SHALL include throughput (documents per hour) and per-stage timing,
computed post-hoc from consecutive audit-record timestamps per document. This
timing is transition-to-transition **wall-clock latency** (it includes any
queue/resume wait between stages), NOT pure stage compute cost, and the report
SHALL label it as such so it is not misread.

#### Scenario: Run report includes timing

- **WHEN** a batch run completes and its report is produced
- **THEN** the report includes documents-per-hour and per-stage timing derived
  from audit-record timestamps
